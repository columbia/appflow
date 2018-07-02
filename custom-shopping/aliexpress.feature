Feature: aliexpress
    @app
    Scenario: skip promotion
        Given screen is app_aliexpress_promotion
        Then click !id:'closebtn'

    @app
    Scenario: skip tutorial
        Given screen is app_aliexpress_tutorial
        Then click !id:'tv_tv2'

    @app
    Scenario: choose options
        Given screen is app_aliexpress_option
        Then click !class:'CompoundButton'
        And click !marked:'Continue'

    @app
    Scenario: skip tutorial2
        Given screen is app_aliexpress_tutorial2
        Then click !marked:'btn_got_it'

    @app
    Scenario: select everything
        Given screen is app_aliexpress_precart
        Then click !id:'select_all'

    @app
    Scenario: select address
        Given screen is app_aliexpress_seladdr
        Then click !textcontains:'New York'

    @bridge
    Scenario: add credit card
        Given screen is checkout
        When click tv_payment_option_non_bind_card_title
        Then screen is cardedit

    @override
    Scenario: change count [with buttons]
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click bt_quantity_plus
        And seein @item_count '2'
        And click bt_quantity_minus
        And seein @item_count '1'
        And screen is cart


