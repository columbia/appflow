Feature: hm

    @app
    Scenario: select country
        Given screen is app_hm_country
        Then click !marked:'United States'

    @app
    Scenario: select option
        Given screen is app_hm_option
        Then click !textcontains:'4-6'

    @override
    @bridge
    Scenario: remove [through long click]
        Given screen is cart
        And cart_filled is true
        When longclick !marked:'bag_item_layout_details'
        Then set cart_filled to false

    @override
    @bridge
    Scenario: login from account
        Given screen is menu
        And loggedin is false
        When click !marked:'My H&M'
        And click !marked:'Log in'
        Then screen is signin

    @bridge
    Scenario: enter card info
        Given screen is checkout
        When click Enter card information
        Then screen is cardedit

    @override
    @bridge
    Scenario: change address
        Given screen is checkout
        When click DELIVERY INFORMATION
        And click Change delivery address
        Then screen is address
