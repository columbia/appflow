Feature: register
    Scenario: see email
        Given screen is register
        Then see @email

    Scenario: see password
        Given screen is register
        Then see @password

    Scenario: old user
        Given screen is register
        When click @signin
        Then screen is signin

    Scenario: cancel register
        Given screen is register
        When click @back
        Then screen is not register
