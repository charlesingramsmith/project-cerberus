# Password reset: one-time Supabase setup

"Forgot your password?" on the sign-in screen asks Supabase to email a reset link. Two
settings in the Supabase dashboard decide whether that email arrives and whether its link
works. You only do this once. Nothing here goes in the code or in `secrets.toml`.

## 1. Point the reset link at the app

Supabase's standard email link doesn't work with a Streamlit app: it hands the sign-in back
either in a part of the address the app can't read, or in a form that needs a secret from
the browser tab that asked for the email, which is long gone by the time you open it. So the email has to link straight to
the app with a one-time token in the address, which the app then checks.

1. Supabase dashboard > **Authentication** > **Emails** > **Templates** > **Reset password**
   (older dashboards call it "Reset Password" under Email Templates).
2. Replace the message body with:

   ```html
   <h2>Reset your Project Cerberus password</h2>
   <p>Someone (hopefully you) asked to reset the password for this email address.</p>
   <p><a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery">Choose a new password</a></p>
   <p>The link works once, for an hour. If you didn't ask for this, you can ignore this email.</p>
   ```

3. Save.

`{{ .RedirectTo }}` is the app's own address (the app sends it with each request), so the
same template works for the live site and for `localhost`. It has to be allowed under
**Authentication** > **URL Configuration** > **Redirect URLs**: the `<app url>/**` entries
you added for Google sign-in already cover it. If it isn't allowed, Supabase uses the
**Site URL** instead, so set that to the live app's address.

## 2. Make sure the email can be delivered

Supabase's built-in email service is only meant for trying things out: it sends a handful
of emails an hour, and (on current plans) only to the email addresses of your own
Supabase team members. To send reset emails to everyone, set up your own email provider
under **Authentication** > **Emails** > **SMTP Settings** (Supabase's docs list providers
such as Resend, Postmark or SendGrid; most have a free tier).

If the limit is hit, the app shows Supabase's own message (for example "email rate limit
exceeded").

## Checking it works

1. On the live app, sign out, open **Forgot your password?**, enter your email and tap
   **Email me a reset link**.
2. Open the email and tap the link. The app should open on **Choose a new password**.
3. Choose one, then sign out and back in with it.

In demo mode (no Supabase keys) no email is sent: the app shows an **Open the reset link**
button instead, so the flow can be tried and tested.
