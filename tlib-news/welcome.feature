Feature: welcome
    Scenario: signin
        Given screen is welcome
        When click @existing
        Then screen is signin

    Scenario: signup
        Given screen is welcome
        When click @newuser
        Then screen is signup

    Scenario: skip
        Given screen is welcome
        Then click @skip
