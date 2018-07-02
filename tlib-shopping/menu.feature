Feature: menu

    Scenario: to main
        Given screen is menu
        When click @home
        Then screen is main

    Scenario: to settings
        Given screen is menu
        When click @setting
        Then screen is setting

    Scenario: to account [signed in]
        Given screen is menu
        And loggedin is true
        When click @account
        Then screen is account

    @mainX
    Scenario: click account [not signed in, to signin]
        Given screen is menu
        And loggedin is false
        When click @account
        Then screen is signin

    Scenario: click account [not signed in, goto welcome]
        Given screen is menu
        And loggedin is false
        When click @account
        Then screen is welcome

    Scenario: to cat
        Given screen is menu
        When click @cat
        Then screen is cat

    Scenario: to cart
        Given screen is menu
        When click @cart
        Then screen is cart

    @cleantest
    @register
    Scenario: click signin [to signin]
        Given screen is menu
        And loggedin is false
        When click @signin
        Then screen is signin

    Scenario: click signin [to welcome]
        Given screen is menu
        And loggedin is false
        When click @signin
        Then screen is welcome

    Scenario: close menu
        Given screen is menu
        #And app is not com.newegg.app
        When back
        Then screen is not menu
        And set menu_extended to false

    Scenario: to faq
        Given screen is menu
        When click @faq
        Then screen is help

    Scenario: to customer service
        Given screen is menu
        And loggedin is true
        When click @contact
        #Then screen is contact

    Scenario: to help
        Given screen is menu
        When click @help
        Then screen is help

    Scenario: to about
        Given screen is menu
        When click @about
        Then screen is about

    Scenario: to notification
        Given screen is menu
        And loggedin is true
        When click @notifications
        Then screen is notif

    Scenario: logout [to signin]
        Given screen is menu
        And loggedin is true
        When click @logout
        Then screen is signin
        And set loggedin to false
        And set cart_filled to false

    Scenario: logout [to welcome]
        Given screen is menu
        And loggedin is true
        When click @logout
        Then screen is welcome
        And set loggedin to false
        And set cart_filled to false

    Scenario: logout [to main]
        Given screen is menu
        And loggedin is true
        When click @logout
        Then screen is main
        And set loggedin to false
        And set cart_filled to false

    Scenario: see invite
        Given screen is menu
        Then see @invite

    Scenario: see giftcard
        Given screen is menu
        Then see @giftcard

    Scenario: see order history
        Given screen is menu
        And loggedin is true
        When click @orders
        Then screen is orders

    Scenario: to terms
        Given screen is menu
        When click @terms
        Then screen is terms
