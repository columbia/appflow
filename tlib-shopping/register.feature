Feature: register

    Scenario: old user
        Given screen is register
        When click @signin
        Then screen is signin

    Scenario: skip
        Given screen is register
        When click @back
        Then screen is not register

    Scenario: register with facebook
        Given screen is register
        Then see @register_fb

    Scenario: register with google
        Given screen is register
        Then see @register_gg

    Scenario: type in basic info
        Given screen is register
        When text @email '@username'
