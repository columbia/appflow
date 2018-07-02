Feature: wanelo
    @app
    Scenario: skip offer
        Given screen is app_wanelo_offer
        Then click sales_popup_close_button

    @bridge
    Scenario: goto notifications
        Given screen is main
        When click profile
        And click settings
        And click Settings
        And click Push Notifications
        Then screen is notif

    @bridge
    Scenario: checkout
        Given screen is detail
        When click Buy
        And click options_container
        And click !textcontains:'11'
        Then screen is checkout

    @bridge
    Scenario: enter addr
        Given screen is checkout
        When click Ship to
        Then screen is addredit

    @bridge
    Scenario: enter card
        Given screen is checkout
        When click Payment
        Then screen is cardedit

    @app
    Scenario: scroll to see items
        Given screen is app_wanelo_needscroll
        When scroll down
        And scroll up
        Then screen is searchret

    @override
    @bridge
    Scenario: filter by category [no confirm step, no click cat]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_category_name'
        And waitidle
        And click @apply
        Then screen is searchret
        And set filtered to true

    @override
    Scenario: filter by price [no confirm step, no click cat]
        Given screen is filter
        And filtered is false
        When click !textcontains:'@filter_price_name'
        And click @apply
        Then screen is searchret
        And set filtered to true


