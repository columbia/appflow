Feature: boxed
    @app
    Scenario: enter zipcode
        Given screen is app_boxed_zipcode
        Then text !id:'zipCode' '10027'
        And click !id:'confirm_action'

    @override
    @bridge
    Scenario: goto checkout [reach payment, signed in]
        Given screen is cart
        And loggedin is true
        And cart_filled is true
        When click @checkout
        Then screen is payment
