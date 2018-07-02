Feature: charlotte
    @override
    @bridge
    Scenario: remove item and exit cart
        Given screen is cart
        And cart_filled is true
        When click @item_remove
        Then screen is not cart
        And set cart_filled to false

    @observe
    Scenario: can't reach cart when empty
        Given screen is main
        When click @cart
        Then screen is main
        And set cart_filled to false

    @bridge
    Scenario: extend menu
        Given screen is menu
        When click MORE
        Then screen is menu
        And set menu_extended to true

    @bridge
    Scenario: checkout to cardedit
        Given screen is checkout
        When click @payments
        Then screen is cardedit

    @override
    Scenario: change count [click on triangle]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click spinner
        And click @item_count_2
        And seein @item_count '2'
        And click spinner
        And click @item_count_1
        And seein @item_count '1'
        And screen is cart

    @override
    Scenario: to customer service [extend menu]
        Given screen is menu
        And menu_extended is true
        When click CUSTOMER SERVICE
        Then screen is contact

    @override
    @bridge
    Scenario: to notification [extend menu]
        Given screen is menu
        And menu_extended is false
        When click MORE
        And click NOTIFICATIONS
        Then screen is notif

    @override
    @bridge
    Scenario: to terms [extend menu]
        Given screen is menu
        And menu_extended is false
        When click MORE
        And click TERMS OF USE
        Then screen is terms

    @override
    @bridge
    Scenario: to faq [extend menu]
        Given screen is menu
        And menu_extended is false
        When click MORE
        And click FAQs
        Then screen is help
