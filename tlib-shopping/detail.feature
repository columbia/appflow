Feature: detail

    Scenario: see item title
        Given screen is detail
        Then see @detail_title

    Scenario: see item image
        Given screen is detail
        Then see @detail_image

    Scenario: click the image
        Given screen is detail
        When click @detail_image
        And back
        Then screen is detail

    Scenario: add to cart [cart empty, stay at detail]
        Given screen is detail
        And loggedin is false
        And cart_filled is false
        When click @detail_addcart
        And waitidle
        And click @cart
        And not seetext '@empty_cart_msg'
        Then screen is cart
        And set cart_filled to true

    Scenario: add to cart [cart empty, goto cart]
        Given screen is detail
        And loggedin is false
        And cart_filled is false
        And filtered is false
        When click @detail_addcart
        And waitidle
        And not seetext '@empty_cart_msg'
        Then screen is cart
        And set cart_filled to true

    @cleantest
    Scenario: add to cart [cart empty, signed in, stay at detail]
        Given screen is detail
        And loggedin is true
        And cart_filled is false
        And filtered is false
        When click @detail_addcart
        And waitidle
        And click @cart
        And not seetext '@empty_cart_msg'
        Then screen is cart
        And set cart_filled to true

    @cleantest
    Scenario: add to cart [cart empty, signed in, goto cart]
        Given screen is detail
        And loggedin is true
        And cart_filled is false
        And filtered is false
        When click @detail_addcart
        And waitidle
        And not seetext '@empty_cart_msg'
        Then screen is cart
        And set cart_filled to true

    @cartX
    Scenario: go to cart
        Given screen is detail
        And loggedin is false
        When click @cart
        Then screen is cart

    Scenario: go to cart [signed in]
        Given screen is detail
        And loggedin is true
        When click @cart
        Then screen is cart

    Scenario: see share
        Given screen is detail
        Then see @share
