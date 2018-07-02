Feature: jane
    @app
    Scenario: select option
        Given screen is app_jane_option
        Then click !id:'trait_item_option_ll'
        And click !id:'option_item_title_tv'

    @app
    Scenario: continue shopping
        Given screen is app_jane_continue
        Then click !marked:'CONTINUE SHOPPING'

    @app
    Scenario: confirm logout
        Given screen is app_jane_logout_confirm
        Then click LOG OUT
