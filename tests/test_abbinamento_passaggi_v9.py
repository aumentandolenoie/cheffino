from importa_foto_passaggi import steps_equivalent, ImagesHTML, associate_steps, IMAGE_VERSION


def test_minor_editorial_rewording_can_keep_photo_mapping():
    source = ["Lava i pomodorini, quindi tagliali a metà 1.",
              "Scalda l'olio, aggiungi il basilico 2.",
              "Mescola la pasta con il condimento 3."]
    stored = ["Lava i pomodorini, quindi tagliali a metà.",
              "Scalda l’olio, aggiungi il basilico.",
              "Mescola la pasta con il condimento."]
    assert steps_equivalent(source, stored)


def test_rewritten_recipe_must_not_receive_automatic_photos():
    source = ["Soffriggi con olio e aglio.", "Cuoci i pomodori.", "Condisci la pasta."]
    stored = ["Cuoci la pasta.", "Prepara una crema di ricotta.", "Unisci tutto."]
    assert not steps_equivalent(source, stored)


def test_fused_or_split_steps_must_be_rejected():
    assert not steps_equivalent(["Lava gli ingredienti.", "Cuoci tutto."],
                                ["Lava gli ingredienti e cuoci tutto."])


def test_photo_parser_uses_numbered_images_when_step_text_is_verified():
    source = ["Lava i pomodorini, quindi tagliali a metà 1.",
              "Scalda l'olio, aggiungi il basilico 2.",
              "Mescola la pasta con il condimento 3."]
    stored = ["Lava i pomodorini, quindi tagliali a metà.",
              "Scalda l’olio, aggiungi il basilico.",
              "Mescola la pasta con il condimento."]
    parser = ImagesHTML("Pasta", "https://ricette.giallozafferano.it/Pasta.html")
    parser.feed(''.join(f'<img alt="Pasta - {i}" src="https://www.giallozafferano.it/images/236-23641/a_{i}.jpg">' for i in range(1,4)))
    assert steps_equivalent(source, stored)
    groups, method = associate_steps(parser, source, len(stored))
    assert method == 'numbered'
    assert len(groups) == 3
    assert IMAGE_VERSION == 9
