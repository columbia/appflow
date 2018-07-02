Feature: contact

    Scenario: see contact-by-phone
        Given screen is contact
        Then see @phone

    Scenario: see contact-by-email
        Given screen is contact
        Then see @email
