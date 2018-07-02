Feature: account

    Scenario: return to last screen
        Given screen is account
        Then back

    Scenario: to address
        Given screen is account
        When click @addresses
        Then screen is address

    Scenario: to payment
        Given screen is account
        When click @payments
        Then screen is payment
