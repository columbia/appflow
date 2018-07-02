Feature: checkout

    Scenario: show shipping cost
        Given screen is checkout
        Then see @shippingcost

    Scenario: show subtotal
        Given screen is checkout
        Then see @subtotal

    Scenario: show tax
        Given screen is checkout
        Then see @tax

    Scenario: show total
        Given screen is checkout
        Then see @totalcost

    Scenario: go to address
        Given screen is checkout
        When click @addresses
        Then screen is address

    Scenario: go to payment
        Given screen is checkout
        When click @payments
        Then screen is payment
