import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, spacing, fonts } from '@/src/utils/theme';

type Package = {
  id: string;
  name: string;
  price_usd: number;
  original_price_usd: number;
  hashrate_boost_ghs: number;
  hashrate_display?: string;
};

export default function CrossSellBanner({
  data,
  onPress,
}: {
  data:
    | {
        available: boolean;
        headline?: string;
        price_label?: string;
        original_price_label?: string;
        discount_pct?: number;
        package?: Package;
        cta?: string;
      }
    | null
    | undefined;
  onPress?: () => void;
}) {
  const router = useRouter();
  if (!data?.available || !data.package) return null;
  const headline = data.headline || '+100%!! More Computing Power';
  const priceLbl = data.price_label || `$${data.package.price_usd.toFixed(2)}!`;
  const origLbl = data.original_price_label || `$${data.package.original_price_usd.toFixed(2)}`;

  const handlePress = () => {
    if (onPress) return onPress();
    router.push(`/(tabs)/shop?focus=${data.package!.id}`);
  };

  return (
    <TouchableOpacity activeOpacity={0.85} onPress={handlePress} style={styles.wrap} testID="cross-sell-banner">
      <LinearGradient
        colors={['#FF9F0A', '#FF7A00']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.banner}
      >
        <View style={styles.row}>
          <View style={styles.iconBox}>
            <Ionicons name="flash" size={22} color="#fff" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.headline} numberOfLines={1}>
              {headline}
            </Text>
            <View style={styles.priceRow}>
              <Text style={styles.priceNow}>{priceLbl}</Text>
              <Text style={styles.priceOrig}>{origLbl}</Text>
              {data.discount_pct ? (
                <View style={styles.pill}>
                  <Text style={styles.pillText}>-{data.discount_pct}%</Text>
                </View>
              ) : null}
            </View>
          </View>
          <Ionicons name="chevron-forward" size={22} color="#fff" />
        </View>
      </LinearGradient>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.md },
  banner: {
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconBox: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.22)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headline: { color: '#fff', fontSize: 14, fontWeight: '800', letterSpacing: -0.2 },
  priceRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  priceNow: { color: '#fff', fontSize: 18, fontWeight: '900', fontFamily: fonts.mono },
  priceOrig: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 12,
    fontFamily: fonts.mono,
    textDecorationLine: 'line-through',
  },
  pill: {
    backgroundColor: 'rgba(0,0,0,0.25)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  pillText: { color: '#fff', fontSize: 11, fontWeight: '800' },
});
