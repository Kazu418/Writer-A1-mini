from plotnote.personal_segment import split_word


def test_word_split_groups_disconnected_radicals_and_preserves_all_paths():
    # Two characters, each with two disconnected components.
    paths = [[(0, 0), (1, 10)], [(3, 0), (9, 10)],
             [(12, 0), (13, 10)], [(15, 0), (21, 10)]]
    result = split_word(paths, '生活')
    assert result['partitions'] == [[0, 1], [2, 3]]
    assert result['paths_modified'] is False
    assert result['status'] == 'unreviewed_geometric_split'


def test_connected_characters_are_not_cut_apart():
    assert split_word([[(0, 0), (20, 5)]], '生活') is None


def test_split_does_not_use_stored_stroke_order_as_character_order():
    paths = [[(15, 0), (20, 10)], [(0, 0), (5, 10)]]
    assert split_word(paths, '生活')['partitions'] == [[1], [0]]
