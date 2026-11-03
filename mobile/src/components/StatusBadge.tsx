import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { PostStatus } from '../types';
import { Colors } from '../constants/theme';

interface StatusBadgeProps {
  status: PostStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getBadgeStyle = () => {
    switch (status) {
      case 'published':
        return { bg: Colors.successLight, text: Colors.success, label: 'Published' };
      case 'approved':
        return { bg: '#e0e7ff', text: Colors.primary, label: 'Approved' };
      case 'ready_for_review':
        return { bg: Colors.warningLight, text: Colors.warning, label: 'Ready for Review' };
      case 'draft':
        return { bg: '#f1f5f9', text: Colors.textMuted, label: 'Draft' };
      case 'failed':
        return { bg: Colors.dangerLight, text: Colors.danger, label: 'Failed' };
      case 'scheduled':
        return { bg: '#ede9fe', text: '#7c3aed', label: 'Scheduled' };
      default:
        return { bg: '#f1f5f9', text: Colors.textMuted, label: status };
    }
  };

  const config = getBadgeStyle();

  return (
    <View style={[styles.badge, { backgroundColor: config.bg }]}>
      <Text style={[styles.label, { color: config.text }]}>{config.label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  label: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});

