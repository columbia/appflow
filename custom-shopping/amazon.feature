Feature: amazon
    @app
    Scenario: ignore promotion
        Given screen is amazon_promotion
        Then click !marked:'Not interested'

    #    @override
    #    Scenario: login [2-step]
    #        Given screen is signin
    #        When text @email '@username'
    #        And click Continue
    #        And text @password '@password'
    #        And click @login
    #        Then screen is not signin
    #        And set loggedin to true
