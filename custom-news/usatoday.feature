Feature: usatoday
    @app
    Scenario: goto setting
        Given screen is app_usatoday_allsetting
        Then click General

    @override
    @bridge
    Scenario: change size [goto setting]
        Given screen is ctxmenu
        When click @textsize
        Then screen is setting
