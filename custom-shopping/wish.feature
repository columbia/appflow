Feature: wish
    @app
    Scenario: select options
        Given screen is app_wish_option
        Then click !id:'add_to_cart_dialog_fragment_list_view'

