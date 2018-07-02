Feature: homedepot
    @app
    Scenario: choose zip
        Given screen is app_homedepot_zip
        Then click !textcontains:'zip'
        And type '10027'
        And wait 1
        And kbdaction
        And wait 3
        And click !marked:'Bronx Terminal #6891'

        #    Scenario: skip tutorial
        #        Given screen is app_homedepot_tutorial
        #        Then scroll right

        #    Scenario: workaround search bug
        #        Given screen is search
        #        When click @search_input
        #        And clearfocused
        #        And type 'mouse'
        #        And click !textcontains:'mouse bait'
        #        Then screen is searchret
        #        And set searched to true

        #    Scenario: signin from main
        #        Given screen is main
        #        When click !Button+marked:'Sign In'
        #        Then screen is signin

    @override
    Scenario: change count [fill in]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And text @item_count '2'
        And seein @item_count '2'
        And text @item_count '1'
        And seein @item_count '1'


