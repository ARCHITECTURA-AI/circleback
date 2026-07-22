import Link from "next/link";

export default function PrivacyPage() {
  return (
    <>
      <h1>Privacy Policy</h1>
      <p className="lead">
        Circle Back is a personal/portfolio project. We take your privacy seriously
        and are committed to being fully transparent about how your data is handled.
      </p>

      <h2>1. What Data We Store</h2>
      <p>When you connect your accounts (Gmail, Slack) to Circle Back, we store:</p>
      <ul>
        <li><strong>OAuth Tokens:</strong> Necessary to access your accounts. These are encrypted at rest using industry-standard Fernet encryption.</li>
        <li><strong>Messages &amp; Threads:</strong> We sync and store messages to extract commitments and monitor for follow-ups.</li>
        <li><strong>Commitments:</strong> The extracted promises you made or are owed.</li>
        <li><strong>Identity Mappings:</strong> Manual mappings between email addresses/Slack IDs and Person records.</li>
      </ul>

      <h2>2. Third-Party LLM Processing</h2>
      <p>
        To extract commitments and detect fulfillment, Circle Back sends the contents of your synced messages to a third-party LLM API. 
        By default, this is Groq&apos;s API (using the Llama model family). Alternatively, the system can be configured to use Anthropic&apos;s Claude API.
        Your data is processed according to the respective provider&apos;s privacy policy and is not used to train their models under standard API terms.
      </p>

      <h2>3. Retention and Deletion</h2>
      <p>
        We store your data as long as your account remains connected. You can permanently delete all your data at any time.
      </p>
      <p>
        <strong>How to delete your data:</strong> Go to your Dashboard, navigate to the Settings panel, and click &quot;Disconnect and Delete My Data&quot;. This performs an absolute purge of all tokens, messages, commitments, and identity mappings from the database. It is not a &quot;soft delete&quot; — the data is permanently erased.
      </p>

      <h2>4. Encryption and Security</h2>
      <p>
        Your OAuth tokens are never stored in plaintext. They are encrypted using Fernet symmetric encryption before being saved to the database.
      </p>

      <div className="mt-8 pt-8 border-t border-slate-200 dark:border-slate-800">
        <Link href="/" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 font-medium">
          &larr; Back to Home
        </Link>
      </div>
    </>
  );
}
