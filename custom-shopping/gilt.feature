Feature: gilt
    Scenario: type card number
        Given screen is addredit
        When text view_edit_credit_card_number '@card_no'
        Then set cardno_filled to true

    Scenario: fill info in checkout
        Given screen is checkout
        When click Add Payment And Shipping Address

    @app
    Scenario: select size
        Given screen is app_gilt_select
        When back
        And click 9.5
        And click Add to Cart
