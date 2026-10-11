from importa_foto_passaggi import ImagesHTML, associate_strips, IMAGE_VERSION


def strips():
    parser=ImagesHTML("Pasta","https://ricette.giallozafferano.it/Pasta.html")
    parser.strips=[
       (1,3,"https://www.giallozafferano.it/images/236-23641/foo_strip_1-3.jpg"),
       (4,6,"https://www.giallozafferano.it/images/236-23641/foo_strip_4-6.jpg")]
    return parser


def test_cropped_strip_parts_follow_numbered_instructions():
    source=["Lava 1 e taglia 2.", "Scalda 3 e mescola 4.",
            "Aggiungi 5, poi servi 6."]
    groups=associate_strips(strips(),source,len(source))
    assert [len(g) for g in groups]==[2,2,2]
    assert groups[0][0].endswith("strip_1-3.jpg#part=0")
    assert groups[1][0].endswith("strip_1-3.jpg#part=2")
    assert groups[1][1].endswith("strip_4-6.jpg#part=0")


def test_nonmonotonic_numbers_cannot_split_strips():
    source=["Cuoci 4 poi 1.", "Mescola 2 e 3.", "Completa 5 e 6."]
    assert associate_strips(strips(),source,len(source))==[]


def test_sparse_or_unrelated_numbers_do_not_trigger_crop():
    source=["Mescola un ingrediente.", "Aggiungi un ingrediente.", "Servi 2."]
    assert associate_strips(strips(),source,len(source))==[]


def test_duplicate_variants_do_not_duplicate_cropped_pictures():
    p=strips()
    p.strips.append((1,3,"https://www.giallozafferano.it/images/236-23641/another_strip_1-3.jpg"))
    groups=associate_strips(p,["Metti 1, 2 e 3.", "Metti 4, 5 e 6."],2)
    assert [len(g) for g in groups]==[1,1]
    assert IMAGE_VERSION==11
