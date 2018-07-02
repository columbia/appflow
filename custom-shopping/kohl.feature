Feature: kohl
    @app
    Scenario: I don't love kohl
        Given screen is app_kohl_love
        Then click !marked:'NO'
        And back

    @bridge
    Scenario: checkout to cardedit
        Given screen is checkout
        When click Continue to Payment
        Then screen is cardedit

    @override
    Scenario: change count [by edit]
        Given screen is cart
        And cart_filled is true
        When seein @item_count '1'
        And text @item_count '2'
        Then seein @item_count '2'
        And text @item_count '1'
        Then seein @item_count '1'
