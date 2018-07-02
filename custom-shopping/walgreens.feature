Feature: walgreens
    @app
    Scenario: skip intro
        Given screen is app_walgreens_intro
        Then click !marked:'left_circular_txview'

    @bridge
    Scenario: go shopping
        Given screen is walgreens_menu
        When click !marked:'Shop Products'
        Then screen is main

    @bridge
    Scenario: go to signin
        Given screen is walgreens_menu
        When click !id:'settings'
        And click !id:'menu_login'
        Then screen is signin

    @app
    Scenario: keep shopping
        Given screen is app_walgreens_keepshopping
        Then click !marked:'KEEP SHOPPING'

    @override
    Scenario: change count [with buttons]
        Given screen is cart
        And cart_filled is true
        When seein @item_count '1'
        Then click wag-plus
        And seein @item_count '2'
        Then click wag-minus
        And seein @item_count '1'
        And screen is cart

    @app
    Scenario: open account details
        Given screen is app_walgreens_preaccount
        When click minimized
        Then screen is account
