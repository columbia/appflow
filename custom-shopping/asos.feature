Feature: asos

    @app
    Scenario: skip intro
        Given screen is app_asos_intro
        Then click !marked:'MEN'
        #And click OK, THANKS

    @app
    Scenario: select option
        Given screen is app_asos_option
        #Then click !TextView+text:'Size'
        Then click M

    @app
    Scenario: manual enter
        Given screen is app_asos_manual
        Then click Or enter address manually

    @app
    Scenario: choose credit card
        Given screen is app_paywith
        Then click !textcontains:'credit'

    @override
    Scenario: filter by price [no confirm, slider]
        Given screen is filter
        And filtered is false
        When click Price Range
        When text min_price '0'
        And text max_price '100'
        And click Apply
        Then screen is searchret
        And set filtered to true

    @app
    Scenario: wait for snack to disappear
        Given screen is app_asos_snack
        Then wait 5

    @override
    Scenario: change count [with edit]
        Given screen is cart
        And cart_filled is true
        When click Edit
        And click Qty: 1
        And click Qty: 2
        And click Apply
        Then seein @item_count '2'
        When click Edit
        And click Qty: 2
        And click Qty: 1
        And click Apply
        Then seein @item_count '1'
        And screen is cart
