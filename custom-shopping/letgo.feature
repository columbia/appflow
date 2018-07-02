Feature: letgo

    @app
    Scenario: skip startup screen
        Given screen is app_letgo_startup
        Then click !marked:'Maybe Later'

    @app
    Scenario: skip detail intro
        Given screen is app_letgo_detailintro
        Then click !id:'product_detail_onboarding_close_iv'

    @override
    @bridge
    Scenario: goto sort by scroll
        Given screen is filter
        When scroll down
        And scroll down
        And scroll down
        Then screen is sort
