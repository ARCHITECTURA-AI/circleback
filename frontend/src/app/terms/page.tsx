import Link from "next/link";

export default function TermsPage() {
  return (
    <>
      <h1>Terms of Service</h1>
      <p className="lead">
        Welcome to Circle Back. By using this service, you agree to the following terms.
      </p>

      <h2>1. Nature of the Service</h2>
      <p>
        Circle Back is a personal/portfolio project designed to track commitments across connected platforms (e.g., Gmail, Slack). It is provided "as is" without any warranties of any kind. 
      </p>

      <h2>2. Disclaimer of Liability</h2>
      <p>
        The creators and maintainers of Circle Back are not liable for any damages, missed deadlines, broken commitments, or data loss that may arise from using this software. You use this service entirely at your own risk.
      </p>
      <p>
        <strong>Not Legal Advice:</strong> Nothing provided by this service constitutes legal advice or creates a legally binding contract between you and any third party regarding your commitments.
      </p>

      <h2>3. Acceptable Use</h2>
      <p>
        You agree to only connect accounts that you have the legal right to access and process. You are responsible for ensuring that your use of Circle Back complies with your employer's policies or any other applicable agreements regarding data privacy and third-party AI processing.
      </p>

      <div className="mt-8 pt-8 border-t border-slate-200 dark:border-slate-800">
        <Link href="/" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 font-medium">
          &larr; Back to Home
        </Link>
      </div>
    </>
  );
}
