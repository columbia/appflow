Feature: address

    Scenario: fill in address [fill state]
        Given screen is addredit
        And addr_addr_filled is false
        And addr_name_filled is true
        When text @addr_line1 '@addr_line1'
        And text @addr_zipcode '@addr_zipcode'
        #text @addr_country '@addr_country'
        And text @addr_city '@addr_city'
        And text @addr_state '@addr_state'
        Then screen is addredit
        And set addr_addr_filled to true

    Scenario: fill in address [select state]
        Given screen is addredit
        And addr_addr_filled is false
        And addr_name_filled is true
        When text @addr_line1 '@addr_line1'
        And text @addr_zipcode '@addr_zipcode'
        #text @addr_country '@addr_country'
        And text @addr_city '@addr_city'
        And select @addr_state '@addr_state'
        Then screen is addredit
        And set addr_addr_filled to true

    Scenario: fill in address [select state abbr]
        Given screen is addredit
        And addr_addr_filled is false
        And addr_name_filled is true
        When text @addr_line1 '@addr_line1'
        And text @addr_zipcode '@addr_zipcode'
        #text @addr_country '@addr_country'
        And text @addr_city '@addr_city'
        And select @addr_state '@addr_state_abbr'
        Then screen is addredit
        And set addr_addr_filled to true

    Scenario: fill in phone
        Given screen is addredit
        And addr_phone_filled is false
        And addr_name_filled is true
        When text @addr_phone '@addr_phone'
        Then screen is addredit
        And set addr_phone_filled to true

    Scenario: fill name [full name]
        Given screen is addredit
        And addr_name_filled is false
        When text @addr_name '@addr_name'
        Then screen is addredit
        And set addr_name_filled to true

    Scenario: fill name [first and last]
        Given screen is addredit
        And addr_name_filled is false
        When text @addr_first '@addr_first'
        And text @addr_last '@addr_last'
        Then screen is addredit
        And set addr_name_filled to true

    Scenario: save address [name+addr+phone]
        Given screen is addredit
        And addr_name_filled is true
        And addr_addr_filled is true
        And addr_phone_filled is true
        When click @addr_save
        Then screen is not addredit

    Scenario: save address [name+addr]
        Given screen is addredit
        And addr_name_filled is true
        And addr_addr_filled is true
        When click @addr_save
        Then screen is not addredit

    Scenario: save address before filling
        Given screen is addredit
        And addr_name_filled is false
        When click @addr_save
        Then screen is not address

    Scenario: add address
        Given screen is address
        When click @address_new
        Then screen is addredit

    Scenario: remove address
        Given screen is address
        When click @address_delete
        Then screen is address

    Scenario: select address
        Given screen is address
        When click @address_select
        And click @continue

    Scenario: see address
        Given screen is address
        Then see @address_item

    Scenario: see edit
        Given screen is address
        Then see @address_edit

    Scenario: see delete
        Given screen is address
        Then see @address_delete

    Scenario: see select
        Given screen is address
        Then see @address_select

    Scenario: click address to see options
        Given screen is address
        When not see @address_edit
        And click @address_item
        Then see @address_edit

    Scenario: click option to see options
        Given screen is address
        When click @address_options
        Then see @address_edit
