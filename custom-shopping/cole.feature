Feature: cole
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

    @override
    @bridge
    Scenario: to notifications
        Given screen is menu
        Then click More
        Then click Notifications

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
