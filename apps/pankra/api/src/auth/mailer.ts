export interface SentMail { to: string; subject: string; link: string }

export interface Mailer { send(mail: SentMail): Promise<void> }

/**
 * Development mailer: writes the sign-in link to the server log. A real email service is
 * a deploy-time choice (docs/inputs-checklist.md) and plugs in behind this interface.
 */
export class LogMailer implements Mailer {
  constructor(private log: (msg: string) => void) {}
  async send(mail: SentMail) { this.log(`sign-in link for ${mail.to}: ${mail.link}`); }
}
