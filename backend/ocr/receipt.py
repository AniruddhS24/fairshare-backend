import os
from . import utils
import re


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
            return '.' in word
        except ValueError:
            return False

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

    def parse(self, words):
        prices = [word for word in words if self.isprice(word['text'])]

        # find mode of x coordinates to determine if the price is on the right side
        x_coords = [word['bounding_box'][1]['x'] for word in prices]
        median_x = utils.median(x_coords)
        filtered_prices = [
            word for word in prices if abs(word['bounding_box'][1]['x'] - median_x) < 0.1]
        filtered_prices.sort(key=lambda x: x['bounding_box'][0]['y'])

        # filter words to only include those in the receipt items
        output_items = []
        output_prices = []
        grand_total = 0.0
        epsilon = 0.005
        word_index = 0
        specials_seen = False
        while word_index < len(words) and words[word_index]['bounding_box'][0]['y'] < filtered_prices[0]['bounding_box'][0]['y'] - epsilon:
            word_index += 1
        for i in range(len(filtered_prices)):
            cur_bound = filtered_prices[i]['bounding_box'][0]['y']
            next_bound = filtered_prices[i + 1]['bounding_box'][0]['y'] if i + \
                1 < len(filtered_prices) else filtered_prices[i]['bounding_box'][3]['y'] + epsilon
            item = self.match_price_to_item(
                words, cur_bound-epsilon, next_bound+epsilon, filtered_prices[i]['bounding_box'][0]['x'])
            special = self.is_special_field(item)
            if not special:
                if specials_seen:
                    continue
                output_items.append(item.strip())
                output_prices.append(
                    float(filtered_prices[i]['text'].replace('$', '')))
            else:
                specials_seen = True
                if special == 'total' and self.is_grand_total(item):
                    grand_total = float(
                        filtered_prices[i]['text'].replace('$', ''))
        return output_items, output_prices, grand_total