Feature: walmart

    @app
    Scenario: select shipping method
        Given screen is app_walmart_shipping
        Then click !marked:'Continue'

    @bridge
    Scenario: to payments
        Given screen is menu
        And loggedin is true
        When click Payment Methods
        Then screen is payment
