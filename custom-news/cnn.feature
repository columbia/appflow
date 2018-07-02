Feature: cnn
    @app
    Scenario: show bookmark & share
        Given screen is app_cnn_hide
        Then click fabmenu

    @bridge
    Scenario: show bookmark
        Given screen is list
        Then click my_cnn_icon
