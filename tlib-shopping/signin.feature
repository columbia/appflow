Feature: signin

    @cleantest
    @mainX
    @detailX
    Scenario: login
        Given screen is signin
        And loggedin is false
        When text @email '@username'
        And text @password '@password'
        And click @login
        And wait 5
        Then screen is not signin
        And set loggedin to true

    Scenario: wrong username
        Given screen is signin
        And loggedin is false
        When text @email '@invalid_username'
        And text @password '@password'
        And click @login
        Then screen is signin

    Scenario: wrong pw
        Given screen is signin
        And loggedin is false
        When text @email '@username'
        And text @password '@invalid_password'
        And click @login
        Then screen is signin

    Scenario: no pw
        Given screen is signin
        And loggedin is false
        When text @email '@username'
        And text @password ''
        And click @login
        Then screen is signin

    Scenario: see forgot
        Given screen is signin
        And loggedin is false
        When see @signin_forgot
        Then screen is signin

    @registerX
    Scenario: new user
        Given screen is signin
        When click @signup
        Then screen is register

    Scenario: skip signin
        Given screen is signin
        And loggedin is false
        When click @back
        Then screen is not signin

    Scenario: signin with google
        Given screen is signin
        Then see @signin_gg

    Scenario: signin with facebook
        Given screen is signin
        Then see @signin_fb
