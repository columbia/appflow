Feature: main

    @signinX
    Scenario: to signin
        Given screen is main
        And loggedin is false
        When click @menu
        And click @signin
        #        click !marked:'@menu_signin'
        Then screen is signin

    @cleantest
    @menuX
    @registerX
    Scenario: to menu
        Given screen is main
        When click @menu
        Then screen is menu

    Scenario: to cart
        Given screen is main
        And loggedin is false
        When click @cart
        Then screen is cart

    Scenario: to cart [not signed in, reach signin]
        Given screen is main
        And loggedin is false
        When click @cart
        Then screen is signin

    @cleantest
    @cartX
    Scenario: to cart [after sign in]
        Given screen is main
        And loggedin is true
        When click @cart
        Then screen is cart

    @cleantest
    @searchX
    @filterX
    Scenario: click searchbox go to search page
        Given screen is main
        #kbdon
        When click @searchbox
        Then screen is search

    @cleantest
    @searchX
    Scenario: click search button go to search page
        Given screen is main
        #kbdon
        When click @search
        Then screen is search

    Scenario: search from main
        Given screen is main
        #kbdon
        When click @searchbox
        And clearfocused
        And type '@search_query'
        And enter
        Then screen is searchret
        And set searched to true

