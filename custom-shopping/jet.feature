Feature: jet
    @app
    Scenario: deal with extra saving
        Given screen is app_jet_extrasaving
        Then text !marked:'zip' '10027'
        And click !marked:'show extra savings'
        And back

    @app
    Scenario: cancel cart preview
        Given screen is app_jet_cartpreview
        Then back

    @app
    Scenario: show filter & sort
        Given screen is app_jet_filterhide
        Then click !id:'fab_filter'

    @override
    @bridge
    Scenario: fill in address [no state]
        Given screen is addredit
        And addr_addr_filled is false
        When text @addr_line1 '@addr_line1'
        And text @addr_zipcode '@addr_zipcode'
        Then set addr_addr_filled to true

    @override
    @bridge
    Scenario: add card
        Given screen is address
        When click ADD NEW PAYMENT METHOD
        Then screen is cardedit

    @bridge
    Scenario: click account, go to address
        Given screen is menu
        And loggedin is true
        When click @account
        Then screen is address

    @override
    Scenario: filter by price [no confirm step, no click first]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_price_name'
        And click @apply
        Then screen is searchret
        And set filtered to true

    @override
    Scenario: change count [with buttons]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click icon_up
        And seein @item_count '2'
        And click icon_down
        And seein @item_count '1'


