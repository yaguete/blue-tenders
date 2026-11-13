export default function PrivacyPage() {
  return (
    <article className="max-w-xl space-y-4 text-sm leading-6">
      <h1 className="text-3xl font-semibold tracking-tight">Privacy</h1>
      <p>
        Search and call pages do not need an account. An account, when configured, stores an email, an
        organisation profile you type yourself, saved calls, alert filters and assistant questions.
      </p>
      <p>
        Alerts are sent only after you submit the form. Each message has an unsubscribe link that works
        without signing in. You can export or delete the demo record with the API routes <code>/me/export</code>{" "}
        and <code>DELETE /me</code>.
      </p>
      <p>
        The assistant is a machine. It quotes the indexed call and does not decide whether you are eligible.
        Hosting is planned in the EU. The model provider, if a key is configured, processes the question
        outside the EU under its own contract. See <code>docs/legal/</code> in the repository.
      </p>
    </article>
  );
}
