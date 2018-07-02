Feature: signin
    @mainX
    @detailX
    Scenario: login
        Given screen is signin
        When text @email '@username'
        And text @password '@password'
        And click @login
        And wait 2
        Then screen is not signin
        And set loggedin to true

    Scenario: wrong username
        Given screen is signin
        When text @email '@invalid_username'
        And text @password '@password'
        And click @login
        Then screen is signin

    Scenario: wrong password
        Given screen is signin
        When text @email '@username'
        And text @password '@invalid_password'
        And click @login
        Then screen is signin

    Scenario: no password
        Given screen is signin
        When text @email '@username'
        And text @password ''
        And click @login
        Then screen is signin

    Scenario: see forgot
        Given screen is signin
        When see @signin_forgot
        Then screen is signin

    @signupX
    Scenario: new user
        Given screen is signin
        When click @signup
        Then screen is register

    Scenario: cancel signin
        Given screen is signin
        When click @back
        Then screen is not signin
