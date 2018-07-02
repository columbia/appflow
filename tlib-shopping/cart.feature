Feature: cart
    Scenario: remove [no confirm dialog]
        Given screen is cart
        And cart_filled is true
        When click @item_remove
        And waitidle
        Then screen is cart
        And seetext '@empty_cart_msg'
        And set cart_filled to false

    Scenario: remove [with confirm dialog]
        Given screen is cart
        And cart_filled is true
        When click @item_remove
        And click @remove_dialog_yes
        And waitidle
        Then screen is cart
        And seetext '@empty_cart_msg'
        And set cart_filled to false

    Scenario: remove [through change count]
        Given screen is cart
        And cart_filled is true
        When click @item_count
        And click @item_count_remove
        And waitidle
        Then screen is cart
        And seetext '@empty_cart_msg'
        And set cart_filled to false

    Scenario: remove [back to main]
        Given screen is cart
        And cart_filled is true
        When click @item_remove
        Then screen is main
        And set cart_filled to false

    Scenario: goto checkout [reach checkout]
        Given screen is cart
        And loggedin is false
        And cart_filled is true
        When click @checkout
        Then screen is checkout

    Scenario: goto checkout [reach checkout, signed in]
        Given screen is cart
        And loggedin is true
        And cart_filled is true
        When click @checkout
        Then screen is checkout

        #    @screen(cart)
        #    @cart_filled(1)
        #    @loggedin()
        #    @expect_screen(addredit)
        #    Scenario: goto checkout [reach address edit]
        #        click @checkout

    Scenario: goto checkout [reach address edit, signed in]
        Given screen is cart
        And loggedin is true
        And cart_filled is true
        When click @checkout
        Then screen is addredit

    Scenario: goto checkout [reach address list, signed in]
        Given screen is cart
        And loggedin is true
        And cart_filled is true
        When click @checkout
        Then screen is address

    Scenario: goto checkout [reach cardedit, signed in]
        Given screen is cart
        And loggedin is true
        And cart_filled is true
        When click @checkout
        Then screen is cardedit

    Scenario: see empty cart
        Given screen is cart
        And cart_filled is false
        Then seetext '@empty_cart_msg'

    Scenario: click thumbnail
        Given screen is cart
        And cart_filled is true
        When click @item_image
        Then screen is detail

    Scenario: see cart count
        Given screen is main
        And cart_filled is true
        Then seein @cart_count '@cart_count_value'

    Scenario: see subtotal
        Given screen is cart
        And cart_filled is true
        Then see @cart_subtotal

    Scenario: see item count
        Given screen is cart
        And cart_filled is true
        Then see @item_count

    Scenario: change count
        Given screen is cart
        And cart_filled is true
        Then seein @item_count '1'
        And click @item_count
        And click @item_count_2
        And seein @item_count '2'
        And click @item_count
        And click @item_count_1
        And seein @item_count '1'
        And screen is cart

    Scenario: close shopping cart
        Given screen is cart
        Then back

    Scenario: return to main
        Given screen is cart
        And cart_filled is true
        And searched is true
        And filtered is false
        And loggedin is true
        Then restart
        And set searched to false

    @observe
    Scenario: observe cart non-empty
        Given screen is cart
        When not seetext '@empty_cart_msg'
        Then set cart_filled to true

    @observe
    Scenario: observe cart empty
        Given screen is cart
        When seetext '@empty_cart_msg'
        Then set cart_filled to false
