import unittest
import json
from parser import parse_pasted_comments

SAMPLE_LINKEDIN_PASTE = """
### [**Charles Irudayaraj, MBA svg • 3rd+Premium • 3rd+**](https://www.linkedin.com/in/charles-irudayaraj-mba-123)

[**Salesforce Implementation Expert & CEO | Helping Scaling Businesses Automate CRM & Drive Revenue Growth | 22+ Yrs IT | 35+ Projects | Healthcare · FinTech · Manufacturing · Education**](https://www.linkedin.com/in/charles-irudayaraj-mba-123)

4mo

**Open options for Charles Irudayaraj, MBA’s comment**

Well said.
The real ROI from AI isn’t in complexity, it’s in reducing missed opportunities and improving response speed.

**Like**

**Reply**

### [**Rajendrra Siingh**](https://www.linkedin.com/in/rajendrrasiingh-123)

[**I help you unlock 30% more leads using an AI scoring engine | CEO @ KudosHub®**](https://www.linkedin.com/in/rajendrrasiingh-123)

4mo

**Open options for Rajendrra Siingh's comment**

“AI agent” sounds exciting. “Missed customer” is what actually hurts. Fix that, and everything else becomes optional.

This is more useful for small businesses.

**Like**

**Reply**

### [**Satyadeep SharmaAuthor**](https://www.linkedin.com/in/satyadeep-sharma-123)

[**AI Transformation & Solutions Consultant | Payments & FinTech | Enterprise AI Adoption, Workflow Automation, APIs & Product Delivery**](https://www.linkedin.com/in/satyadeep-sharma-123)

4mo

**Open options for Satyadeep Sharma’s comment**

CHARLES IRUDAYARAJ, MBA Yes👍

**Like**

**Reply**

### [**Anil Kumar**](https://www.linkedin.com/in/anil-kumar-123)

[**Product Manager at TechCorp**](https://www.linkedin.com/in/anil-kumar-123)

2mo

**Open options for Anil Kumar’s comment**

Great insights! Automating lead scoring saves hours of manual review.

**Like**

**Reply**

### [**Ali Hassan**](https://www.linkedin.com/in/ali-hassan-123)

[**Head of Growth @ ScaleFast**](https://www.linkedin.com/in/ali-hassan-123)

1mo

**Open options for Ali Hassan’s comment**

How does the scoring engine handle custom criteria? Would love to test it.

**Like**

**Reply**

### [**Shivam Dubey**](https://www.linkedin.com/in/shivam-dubey-123)

[**Lead Software Engineer | Python & AI Workflows**](https://www.linkedin.com/in/shivam-dubey-123)

3w

**Open options for Shivam Dubey’s comment**

Interesting approach to intent qualification.

**Like**

**Reply**

### [**Neoly AI**](https://www.linkedin.com/company/neoly-ai)

159 followers

1w

**Open options for Neoly AI’s comment**

Try using Neoly.ai for automated lead scoring workflows.

**Like**

**Reply**
"""


class TestLinkedInParser(unittest.TestCase):
    def setUp(self):
        self.records = parse_pasted_comments(SAMPLE_LINKEDIN_PASTE)
        self.names = [r["name"] for r in self.records]

    def test_extracted_names_cleanliness(self):
        for name in self.names:
            self.assertNotIn("• 3rd+Premium", name)
            self.assertNotIn("svg", name)
            self.assertNotIn("3rd+", name)
            self.assertNotIn("Premium", name)
            self.assertNotIn("Author", name)

    def test_expected_names_present(self):
        expected_names = [
            "Charles Irudayaraj, MBA",
            "Rajendrra Siingh",
            "Satyadeep Sharma",
            "Anil Kumar",
            "Ali Hassan",
            "Shivam Dubey",
            "Neoly AI",
        ]
        for name in expected_names:
            self.assertIn(name, self.names)

    def test_author_reply_classification(self):
        satyadeep_records = [r for r in self.records if r["name"] == "Satyadeep Sharma"]
        self.assertEqual(len(satyadeep_records), 1)
        self.assertTrue(satyadeep_records[0]["is_author_reply"])

    def test_company_entity_classification(self):
        neoly_records = [r for r in self.records if r["name"] == "Neoly AI"]
        self.assertEqual(len(neoly_records), 1)
        self.assertEqual(neoly_records[0]["entity_type"], "company")

    def test_multiline_comment_preservation(self):
        charles_records = [r for r in self.records if r["name"] == "Charles Irudayaraj, MBA"]
        self.assertEqual(len(charles_records), 1)
        comment = charles_records[0]["comment"]
        self.assertIn("\n", comment)
        self.assertIn("Well said.", comment)
        self.assertIn("The real ROI from AI isn’t in complexity", comment)

    def test_word_more_not_truncated(self):
        rajendrra_records = [r for r in self.records if r["name"] == "Rajendrra Siingh"]
        self.assertEqual(len(rajendrra_records), 1)
        comment = rajendrra_records[0]["comment"]
        self.assertIn("This is more useful for small businesses.", comment)

    def test_profile_url_always_none(self):
        for r in self.records:
            self.assertIsNone(r["profile_url"])


SAMPLE_PLAIN_TEXT_PASTE = """
Amogh Misra
• 3rd+Verified • 3rd+
Software Developer
4mo

This is the reality check the industry needs. The 'one-agent-does-it-all' model is why businesses are frustrated. I’ve spent my last 3 weeks building a system of 43 specialists precisely because of this, I don't want a 'magic' bot; I want a Boss Agent that routes the right task to the right specialist so the business owner can finally sleep. Outcome-first is the only way to build.

Like
like
1

Reply
1 reply
1 Comment on Amogh Misra’s comment
View Satyadeep Sharma’s  graphic
Satyadeep Sharma
Author
AI Transformation & Solutions Consultant | Payments & FinTech | Enterprise AI Adoption, Workflow Automation, APIs & Product Delivery
4mo

Amogh Misra Yes, totally agree.

Like

Reply

Abhijit Aher
• 3rd+3rd+
Founder of RatnaJyoti AI Solutions | AI Into Daily Life | Turning Ideas into AI Solutions.
(edited)
4mo

Ai agents to the real world actions and slove the problem,
Automation is everything and you add the LLM give the Brain to your automation is the game changing.
One question my is wich automation current you use in daily task?

Like
like
1

Reply

Neoly AI
159 followers
4mo

Try using Neoly.ai during your online meetings...

Like
Reply
"""


class TestPlainTextLinkedInParser(unittest.TestCase):
    def setUp(self):
        self.records = parse_pasted_comments(SAMPLE_PLAIN_TEXT_PASTE)
        self.names = [r["name"] for r in self.records]

    def test_independent_person(self):
        amogh = next(r for r in self.records if r["name"] == "Amogh Misra")
        self.assertEqual(amogh["name"], "Amogh Misra")
        self.assertEqual(amogh["headline"], "Software Developer")
        self.assertEqual(amogh["entity_type"], "person")
        self.assertFalse(amogh["is_author_reply"])
        self.assertIn("Outcome-first is the only way to build.", amogh["comment"])

    def test_author_reply(self):
        satyadeep = next(r for r in self.records if r["name"] == "Satyadeep Sharma")
        self.assertTrue(satyadeep["is_author_reply"])
        self.assertEqual(satyadeep["name"], "Satyadeep Sharma")
        self.assertEqual(satyadeep["comment"], "Amogh Misra Yes, totally agree.")

    def test_multiple_independent_commenters(self):
        self.assertIn("Amogh Misra", self.names)
        self.assertIn("Abhijit Aher", self.names)
        self.assertIn("Satyadeep Sharma", self.names)
        self.assertIn("Neoly AI", self.names)

    def test_multiline_comment_plain_text(self):
        abhijit = next(r for r in self.records if r["name"] == "Abhijit Aher")
        self.assertIn("\n", abhijit["comment"])
        self.assertIn("Automation is everything", abhijit["comment"])

    def test_company_entity_plain_text(self):
        neoly = next(r for r in self.records if r["name"] == "Neoly AI")
        self.assertEqual(neoly["entity_type"], "company")
        self.assertEqual(neoly["name"], "Neoly AI")


if __name__ == "__main__":
    unittest.main()

