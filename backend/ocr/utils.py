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
