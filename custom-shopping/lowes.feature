Feature: lowes
    @app
    Scenario: select store
        Given screen is app_lowes_findstore
        Then click !class:'EditText'
        And clearfocused
        And type '10027'
        And enter
        And click !marked:'DONE'

    @app
    Scenario: skip tutorial
        Given screen is app_lowes_tutorial
        Then click !marked:'GOT IT'

    @override
    @bridge
    Scenario: go through checkout
        Given screen is cart
        And loggedin is true
        Then click !textcontains:'Truck Deliver'
        And click UPDATE CART
        And wait 5
        And click CHECK OUT

    @override
    Scenario: change count [with edit]
        Given screen is cart
        And cart_filled is true
        When seein @item_count '1'
        And text @item_count '2'
        Then seein @item_count '2'
        And text @item_count '1'
        Then seein @item_count '1'
        And screen is cart
