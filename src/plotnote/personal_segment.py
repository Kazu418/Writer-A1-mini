"""Propose word-to-character splits without trimming or inventing ink."""
import unicodedata


def split_word(paths, labels):
    """Partition horizontal nonoverlapping ink blocks using the known text.

    A hypothesis, never a verified label. Connected characters and stacked
    formulae may have no valid split. Every original path is assigned once.
    """
    if len(labels) < 2 or any(c.isspace() for c in labels):
        return None
    spans = sorted((min(x for x, y in p), max(x for x, y in p), i)
                   for i, p in enumerate(paths) if p)
    if not spans:
        return None
    blocks = []
    for lo, hi, index in spans:
        if blocks and lo <= blocks[-1][1]:
            blocks[-1][1] = max(blocks[-1][1], hi)
            blocks[-1][2].append(index)
        else:
            blocks.append([lo, hi, [index]])
    n, m = len(labels), len(blocks)
    if m < n or m > 100:
        return None
    left, right = blocks[0][0], blocks[-1][1]
    total = right - left
    if total <= 0:
        return None
    weights = [.6 if unicodedata.east_asian_width(c) in ('Na', 'H') else 1 for c in labels]
    expected = [total * w / sum(weights) for w in weights]
    dp = {(0, 0): (0., [])}
    for k in range(1, n + 1):
        for end in range(k, m - (n - k) + 1):
            options = []
            for start in range(k - 1, end):
                previous = dp.get((k - 1, start))
                if previous is None:
                    continue
                lo, hi = blocks[start][0], blocks[end - 1][1]
                width = hi - lo
                cost = ((width - expected[k - 1]) / expected[k - 1]) ** 2
                if end < m:
                    boundary = (hi + blocks[end][0]) / 2
                    ideal = left + sum(expected[:k])
                    cost += .4 * ((boundary - ideal) / expected[k - 1]) ** 2
                options.append((previous[0] + cost, previous[1] + [(start, end)]))
            if options:
                dp[k, end] = min(options, key=lambda value: value[0])
    result = dp.get((n, m))
    if result is None:
        return None
    partitions = [sorted(i for block in blocks[start:end] for i in block[2])
                  for start, end in result[1]]
    assert sorted(i for partition in partitions for i in partition) == list(range(len(paths)))
    return {'partitions': partitions, 'cost': result[0],
            'status': 'unreviewed_geometric_split', 'paths_modified': False}
