import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { Colors, Spacing, Typography } from '../constants/theme';
import { Ionicons } from '@expo/vector-icons';

export const WorkspaceScreen = () => {
  const { user, tenants, activeTenant, selectTenant, serverUrl, updateServerUrl, logout } =
    useAuth();
  const [customUrl, setCustomUrl] = useState(serverUrl);

  const handleSaveUrl = () => {
    updateServerUrl(customUrl);
    Alert.alert('Server Updated', `API endpoint set to: ${customUrl}`);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Profile Card */}
      <View style={styles.card}>
        <View style={styles.userRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{user?.name?.slice(0, 1) || 'U'}</Text>
          </View>
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{user?.name || 'Authorized Member'}</Text>
            <Text style={styles.userEmail}>{user?.email}</Text>
          </View>
        </View>
      </View>

      {/* Workspace Switcher */}
      <Text style={styles.sectionTitle}>Workspaces ({tenants.length})</Text>
      <View style={styles.card}>
        {tenants.map((t) => {
          const isActive = activeTenant?.id === t.id;
          return (
            <TouchableOpacity
              key={t.id}
              style={[styles.workspaceItem, isActive && styles.workspaceItemActive]}
              onPress={() => selectTenant(t)}
            >
              <View style={styles.wsInfo}>
                <View style={[styles.wsIcon, isActive && styles.wsIconActive]}>
                  <Ionicons
                    name="business-outline"
                    size={16}
                    color={isActive ? '#ffffff' : Colors.textMuted}
                  />
                </View>
                <View>
                  <Text style={[styles.wsName, isActive && styles.wsNameActive]}>{t.name}</Text>
                  <Text style={styles.wsSlug}>{t.slug}</Text>
                </View>
              </View>

              {isActive && (
                <View style={styles.activeCheck}>
                  <Ionicons name="checkmark-circle" size={20} color={Colors.primary} />
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Network & Server Settings */}
      <Text style={styles.sectionTitle}>Backend Connection</Text>
      <View style={styles.card}>
        <Text style={styles.inputLabel}>REST API Host URL</Text>
        <TextInput
          style={styles.urlInput}
          value={customUrl}
          onChangeText={setCustomUrl}
          autoCapitalize="none"
          placeholder="http://10.0.2.2:5000"
        />
        <TouchableOpacity style={styles.saveUrlBtn} onPress={handleSaveUrl}>
          <Text style={styles.saveUrlText}>Save Server URL</Text>
        </TouchableOpacity>
      </View>

      {/* Sign Out */}
      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Ionicons name="log-out-outline" size={18} color={Colors.danger} />
        <Text style={styles.logoutBtnText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: Spacing.md,
    paddingBottom: Spacing.xl,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.lg,
  },
  userRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '700',
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.text,
  },
  userEmail: {
    fontSize: 13,
    color: Colors.textMuted,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
    marginLeft: 4,
  },
  workspaceItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f8fafc',
  },
  workspaceItemActive: {
    backgroundColor: '#faf5ff',
    marginHorizontal: -Spacing.md,
    paddingHorizontal: Spacing.md,
    borderRadius: 10,
    borderBottomWidth: 0,
  },
  wsInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  wsIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  wsIconActive: {
    backgroundColor: Colors.primary,
  },
  wsName: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.text,
  },
  wsNameActive: {
    color: Colors.primary,
    fontWeight: '700',
  },
  wsSlug: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  activeCheck: {
    paddingRight: 4,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.text,
    marginBottom: 6,
  },
  urlInput: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: Colors.text,
    marginBottom: Spacing.sm,
  },
  saveUrlBtn: {
    backgroundColor: '#f1f5f9',
    paddingVertical: 9,
    borderRadius: 10,
    alignItems: 'center',
  },
  saveUrlText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.text,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.dangerLight,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  logoutBtnText: {
    color: Colors.danger,
    fontSize: 14,
    fontWeight: '700',
  },
});

