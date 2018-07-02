Feature: zara

    @app
    Scenario: choose all cat
        Given screen is app_zara_searchcat
        Then click !marked:'All'

    @app
    Scenario: choose option
        Given screen is app_zara_option
        Then click !id:'size_cell'
        And click !id:'size_add'

    @override
    @bridge
    Scenario: remove [through menu]
        Given screen is cart
        And cart_filled is true
        When click !id:'product_basket_list_item_more_button'
        And click !marked:'Delete'
        Then set cart_filled to false

    @bridge
    Scenario: goto account
        Given screen is main
        And loggedin is false
        When click !marked:'MY ACCOUNT'
        Then screen is signin

    @bridge
    Scenario: enter card info
        Given screen is checkout
        When click Edit payment method
        And click MasterCard
        Then screen is cardedit

