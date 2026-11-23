import { useEffect, useState } from 'react';
import { Stack, router, useSegments } from 'expo-router';
import { ApiError, api } from '../src/api';

/** Every screen but sign-in needs a session; a 401 sends the athlete to sign in. */
export default function Layout() {
  const segments = useSegments();
  const [checked, setChecked] = useState<string | null>(null);

  useEffect(() => {
    const onSignIn = segments[0] === 'sign-in';
    const key = segments.join('/');
    if (onSignIn || checked === key) return;
    api
      .me()
      .then(() => setChecked(key))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace('/sign-in');
        else setChecked(key); // the API is unreachable: screens show their own errors
      });
  }, [segments, checked]);

  return <Stack screenOptions={{ contentStyle: { backgroundColor: '#f5f5f4' } }} />;
}
