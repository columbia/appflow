Feature: boohoo
    @app
    Scenario: select country
        Given screen is app_boohoo_country
        Then click !textcontains:'United States'
        And click CONTINUE

    @app
    Scenario: choose option
        Given screen is app_boohoo_option
        Then click !marked:'SELECT'
        And click !id:'text'

    @override
    @bridge
    Scenario: sign in
        Given screen is welcome
        When click LOG IN / CREATE ACCOUNT
        And click LOG IN / CREATE ACCOUNT
        Then screen is signin

    @app
    Scenario: choose ship options
        Given screen is app_boohoo_preship
        Then click Country
        And click United States

    @override
    Scenario: filter by color [no confirm step, checkbox only]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_color'
        And click checkBox
        And click APPLY
        Then screen is searchret
        And set filtered to true

    @override
    Scenario: filter by brand [no confirm step, checkbox only]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_brand'
        And click checkBox
        And click APPLY
        Then screen is searchret
        And set filtered to true

    @override
    Scenario: filter by price [no confirm step, checkbox only]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_price'
        And click radio
        And click APPLY
        Then screen is searchret
        And set filtered to true

    @override
    Scenario: filter by size [no confirm step, checkbox only]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_size'
        And click checkBox
        And click APPLY
        Then screen is searchret
        And set filtered to true

    @override
    Scenario: clear filter [with close]
        Given screen is searchret
        And filtered is true
        When click @filter
        And click @filter_reset
        And back
        Then screen is searchret
        And set filtered to false


    @override
    Scenario: change count [with buttons]
        Given screen is cart
        And cart_filled is true
        When seein @item_count '1'
        And click incQuantity
        Then seein @item_count '2'
        And click decQuantity
        Then seein @item_count '1'
        And screen is cart
