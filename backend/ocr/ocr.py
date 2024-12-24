import os
import json
import re
import boto3
import uuid
from auth_utils import authenticate
from http_utils import create_response, create_error_response
from price_utils import formatPrice

textract = boto3.client('textract')
receipts_table = boto3.resource('dynamodb').Table('receipts')
items_table = boto3.resource('dynamodb').Table('items')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def mean(array):
    return sum(array) / len(array)

def std(array):
    return (sum([(x - mean(array)) ** 2 for x in array]) / len(array)) ** 0.5

def median(array):
    array.sort()
    n = len(array)
    if n % 2 == 0:
        return (array[n // 2 - 1] + array[n // 2]) / 2
    else:
        return array[n // 2]

class Receipt:
    def __init__(self):
        self.special_field_keywords = {
            'total': ['subtotal', 'total', 'amount', 'due'],
            'tax': ['tax', 'gst', 'hst', 'pst', 'vat'],
            'gratuity': ['tip', 'gratuity', 'service', 'charge']
        }
        self.total_keywords = [
            r'\btotal\b', r'\btotal amount\b', r'\bgrand total\b', r'\bfinal total\b',
            r'\bamount due\b', r'\bamount payable\b', r'\bbalance due\b', r'\btotal to pay\b'
        ]

    def preprocess_field(self, text):
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text)  # Remove special characters
        return text

    def is_special_field(self, text):
        text = self.preprocess_field(text)
        for field, keywords in self.special_field_keywords.items():
            if any(keyword in text for keyword in keywords):
                return field
        return None

    def is_grand_total(self, text):
        text = self.preprocess_field(text)
        return any(re.search(keyword, text) for keyword in self.total_keywords)

    def isprice(self, word):
        try:
            word = word.replace('$', '')
            float(word)
            return '.' in word or ',' in word
        except ValueError:
            return False

    def detect_prices(self, prices):
        if len(prices) == 0:
            return []
        
        def center_coords(price):
            xc = (price['bounding_box'][0]['x'] + price['bounding_box'][1]['x'])/2
            yc = (price['bounding_box'][0]['y'] + price['bounding_box'][1]['y'])/2
            return xc, yc
        
        prices_sorted = sorted(prices, key=lambda x: x['bounding_box'][0]['y'])
        med_gap = median([prices_sorted[i]['bounding_box'][0]['y'] - prices_sorted[i-1]['bounding_box'][0]['y'] for i in range(1, len(prices_sorted))])
        x_tol = 0.1 # 10% tolerance for horizontal difference (assume prices aligned vertically)
        y_tol = med_gap*1.1 # 10% extra tolerance from median gap

        price_groups = []
        current_group = [prices_sorted[0]]
        for i in range(1, len(prices_sorted)):
            xc_cur, yc_cur = center_coords(prices_sorted[i])
            xc_prev, yc_prev = center_coords(current_group[-1])
            x_diff = abs(xc_cur - xc_prev)
            y_diff = abs(yc_cur - yc_prev)
            if y_diff < y_tol and x_diff < x_tol:
                current_group.append(prices_sorted[i])
            else:
                price_groups.append(current_group)
                current_group = [prices_sorted[i]]
        price_groups.append(current_group)

        # Receipt prices is likely the largest group
        largest_group = 0
        for i in range(1, len(price_groups)):
            if len(price_groups[i]) > len(price_groups[largest_group]):
                largest_group = i
        
        res = []
        for i in range(largest_group, len(price_groups)):
            res.extend(price_groups[i])

        return res


    def match_price_to_item(self, words, min_y, max_y, price_x):
        best = []
        for word in words:
            word_top = word['bounding_box'][0]['y']
            word_bottom = word['bounding_box'][2]['y']
            word_x = word['bounding_box'][0]['x']
            if word_bottom < min_y or word_top > max_y or self.isprice(word['text']) or abs(price_x - word_x) < 0.1:
                continue
            word_height = word_bottom - word_top
            bottom = min(max_y, word_bottom)
            top = max(min_y, word_top)
            overlap_percent = (bottom - top) / word_height
            if overlap_percent > 0.75:
                best.append(word['text'])

        return ' '.join(best)

    def parse_item_quantity(self, item):
        item = item.strip()
        # Match patterns for various item formats
        # "item 2x" or "item x 2"
        match = re.match(r'^(.*?)(?:\s*(\d+)\s*x?)$', item)
        if match:
            item_name = match.group(1).strip().replace('x', '')  # Remove "x" from item name
            quantity = int(match.group(2)) if match.group(2) else 1
            return quantity, item_name.strip()
        # "2 x item" or "item x 2"
        match = re.match(r'^\s*(\d+)\s*x?\s*(.*)$', item)
        if match:
            item_name = match.group(2).strip().replace('x', '')  # Remove "x" from item name
            quantity = int(match.group(1))
            return quantity, item_name.strip()
        # "item (2)" or "item (2x)" or "item (spicy) (2x)"
        match = re.match(r'^(.*?)\s*\(\s*(\d+)\s*x?\s*\)', item)
        if match:
            item_name = match.group(1).strip().replace('x', '')  # Remove "x" from item name
            quantity = int(match.group(2))
            return quantity, item_name.strip()
        # Fallback to return (1, item) if no quantity is found
        return 1, item.strip()
    
    def parse(self, words):
        prices = [word for word in words if self.isprice(word['text'])]

        filtered_prices = self.detect_prices(prices)
        # find mode of x coordinates to determine if the price is on the right side
        # x_coords = [word['bounding_box'][1]['x'] for word in prices]
        # median_x = median(x_coords)
        # filtered_prices = [
        #     word for word in prices if abs(word['bounding_box'][1]['x'] - median_x) < 0.1]
        # filtered_prices.sort(key=lambda x: x['bounding_box'][0]['y'])

        # filter words to only include those in the receipt items
        output_items = []
        output_quantities = []
        output_prices = []
        grand_total = 0.0
        epsilon = 0.005
        word_index = 0
        specials_seen = False
        while word_index < len(words) and len(filtered_prices) > 0 and words[word_index]['bounding_box'][0]['y'] < filtered_prices[0]['bounding_box'][0]['y'] - epsilon:
            word_index += 1
        for i in range(len(filtered_prices)):
            cur_bound = filtered_prices[i]['bounding_box'][0]['y']
            next_bound = filtered_prices[i + 1]['bounding_box'][0]['y'] if i + \
                1 < len(filtered_prices) else filtered_prices[i]['bounding_box'][3]['y'] + epsilon
            item = self.match_price_to_item(
                words, cur_bound-epsilon, next_bound+epsilon, filtered_prices[i]['bounding_box'][0]['x'])
            special = self.is_special_field(item)
            if not special:
                if specials_seen: # Skip if we've seen special fields
                    continue
                quantity, name = self.parse_item_quantity(item)
                # Prevent serial number from being interpreted as quantity
                quantity = 1 if quantity > 100 or quantity < 1 else quantity
                output_items.append(name)
                output_quantities.append(quantity)
                output_prices.append(
                    float(filtered_prices[i]['text'].replace('$', ''))/quantity)
            else:
                specials_seen = True
                if special == 'total' and self.is_grand_total(item):
                    grand_total = float(
                        filtered_prices[i]['text'].replace('$', ''))
        return output_items, output_quantities, output_prices, grand_total

@authenticate
def receipt_ocr(event, context):
    packet = json.loads(event.get('body'))
    receipt_id = packet.get('key')
    response = textract.detect_document_text(
        Document={
            'S3Object': {
                'Bucket': BUCKET_NAME,
                'Name': f'{receipt_id}'
            }
        }
    )
    words = []
    for item in response['Blocks']:
        if item['BlockType'] == 'WORD':
            bounding_box = item['Geometry']['BoundingBox']
            bounding_box_fmt = [
                {'x': bounding_box['Left'],
                 'y': bounding_box['Top']},
                {'x': bounding_box['Left'] + bounding_box['Width'],
                 'y': bounding_box['Top']},
                {'x': bounding_box['Left'] + bounding_box['Width'],
                 'y': bounding_box['Top'] + bounding_box['Height']},
                {'x': bounding_box['Left'],
                 'y': bounding_box['Top'] + bounding_box['Height']}]
            words.append(
                {'text': item['Text'], 'bounding_box': bounding_box_fmt})

    receipt_model = Receipt()
    items, quantities, prices, grand_total = receipt_model.parse(words)
    shared_cost = grand_total - sum([prices[i]*quantities[i] for i in range(len(prices))])
    if shared_cost < 0:
        print('Shared cost is negative')
        grand_total = sum(prices)
        shared_cost = 0

    item_ids = []
    for i in range(len(items)):
        item_id = uuid.uuid4().hex
        item_ids.append(item_id)
        try:
            items_table.put_item(
                Item={
                    'id': str(item_id),
                    'receipt_id': str(receipt_id),
                    'name': items[i],
                    'quantity': str(quantities[i]),
                    'price': formatPrice(prices[i])
                }
            )
        except Exception as e:
            return create_error_response(500, str(e))
    try:
        receipts_table.put_item(
            Item={
                'id': str(receipt_id),
                'image_url': f'https://{BUCKET_NAME}.s3.amazonaws.com/{receipt_id}',
                'shared_cost': formatPrice(shared_cost),
                'grand_total': formatPrice(grand_total),
            }
        )
    except Exception as e:
        return create_error_response(500, str(e))

    return create_response(200, {'message': 'Receipt processed successfully'})