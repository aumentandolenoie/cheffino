from importa_foto_passaggi import ImagesHTML, associate_numbered, associate_strips, IMAGE_VERSION


def parser_with_images(numbered=(),strips=()):
    p=ImagesHTML("Pasta","https://ricette.giallozafferano.it/Pasta.html")
    p.photos={n:f"https://www.giallozafferano.it/images/236-23641/a_{n}.jpg" for n in numbered}
    p.strips=[(start,end,f"https://www.giallozafferano.it/images/236-23641/strip_{start}-{end}_{v}.jpg")
              for start,end,v in strips]
    return p


def test_numbered_partial_album_maps_only_referenced_images():
    p=parser_with_images(numbered=(1,2,4,5,6))
    source=["Taglia le verdure 1 e poi lava tutto 2.",
            "Scalda la padella 3 e rosola 4.",
            "Mescola 5 e impiatta 6."]
    groups=associate_numbered(p,source,3)
    assert groups and len(groups)==3
    assert len(groups[0])==2
    assert len(groups[1])==1
    assert len(groups[2])==2


def test_strip_duplicates_deduplicated_and_partials_mapped():
    p=parser_with_images(strips=((1,3,"a"),(1,3,"b"),(4,6,"a"),(4,6,"b")))
    source=["Prepara le verdure 1, sciacqua 2, taglia 3.",
            "Condisci 4, mescola 5, servi 6.",
            "Completa la decorazione."]
    groups=associate_strips(p,source,3)
    assert groups and [len(g) for g in groups]==[1,1,0]


def test_non_monotone_photo_numbers_not_matched():
    p=parser_with_images(numbered=(1,2,3,4))
    source=["Usa il passaggio 3.", "Torna a 1.", "Poi 2 e 4."]
    # La procedura riscritta / invertita non deve avere associazione automatica
    assert associate_numbered(p,source,3)==[]


def test_strip_intervals_spanning_distinct_steps_not_assigned():
    p=parser_with_images(strips=((1,3,"a"),))
    source=["Prepara 1 e 2.", "Completa 3."]
    assert associate_strips(p,source,2)==[]
    assert IMAGE_VERSION==10
