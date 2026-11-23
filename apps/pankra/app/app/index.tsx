import { Redirect } from 'expo-router';
import { ActivityIndicator, Text } from 'react-native';
import { useSession } from '../src/session';
import { Button, Screen, styles } from '../src/ui';

export default function Home() {
  const { me, loading, signOut } = useSession();
  if (loading) return <Screen><ActivityIndicator accessibilityLabel="Loading" /></Screen>;
  if (!me) return <Redirect href="/sign-in" />;
  return (
    <Screen>
      <Text accessibilityRole="header" style={styles.title}>PANKRA</Text>
      <Text style={styles.body}>Signed in as {me.email}.</Text>
      <Button label="Sign out" onPress={() => void signOut()} />
    </Screen>
  );
}
