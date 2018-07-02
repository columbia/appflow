Feature: dailyhunt
    @app
    Scenario: select language
        Given screen is app_dailyhunt_language
        Then click English
        And click onboarding_continue

    @bridge
    Scenario: go to search
        Given screen is list
        Then click Books
        And click action_search

    Scenario: goto signin
        Given screen is menu
        And loggedin is false
        Then click @signin

    @bridge
    Scenario: goto password
        Given screen is signin
        When text @email '@username'
        And click @login
        And wait 2
        Then screen is dailyhunt_signin_password

    @override
    Scenario: wrong username
        Given screen is signin
        When text @email '@invalid_username'
        And click @login
        And wait 2
        Then screen is signin

    @override
    @bridge
    Scenario: login
        Given screen is dailyhunt_signin_password
        When text @password '@password'
        And click @login
        Then screen is not dailyhunt_signin_password
        And set loggedin to true

    @bridge
    Scenario: goto signon
        Given screen is signin
        When text @email '@newusername'
        And click @login
        And wait 2
        Then screen is dailyhunt_signon_password

    @override
    Scenario: wrong password
        Given screen is dailyhunt_signin_password
        When text @password '@invalid_password'
        And click @login
        Then screen is dailyhunt_signin_password

    @override
    Scenario: no password
        Given screen is dailyhunt_signin_password
        When text @password ''
        And click @login
        Then screen is dailyhunt_signin_password

    @override
    Scenario: see forgot
        Given screen is dailyhunt_signin_password
        When see @signin_forgot
        Then screen is dailyhunt_signin_password

    @override
    Scenario: cancel signin
        Given screen is dailyhunt_signin_password
        When click @back
        Then screen is not dailyhunt_signin_password

    @override
    Scenario: see password
        Given screen is dailyhunt_signon_password
        Then see @password

    @override
    Scenario: cancel register
        Given screen is dailyhunt_signon_password
        When click @back
        Then screen is not dailyhunt_signon_password
