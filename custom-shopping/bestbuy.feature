Feature: bestbuy

    @override
    Scenario: change count [with buttons]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click plus_button
        # bestbuy has some free gift...
        And seein toolbarTitle '4'
        And click minus_button
        And seein @item_count '1'
        And screen is cart

    @override
    @bridge
    Scenario: to address [from menu]
        Given screen is account
        And loggedin is true
        When click Menu
        And click !LABEL+marked:'Profile'
        And click Shipping Addresses
        Then screen is address

    @override
    @bridge
    Scenario: to payment [from menu]
        Given screen is account
        And loggedin is true
        When click Menu
        And click !LABEL+marked:'Profile'
        And click Credit Cards
        Then screen is payment
