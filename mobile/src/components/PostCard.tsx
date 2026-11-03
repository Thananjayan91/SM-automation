import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { PostSummary } from '../types';
import { StatusBadge } from './StatusBadge';
import { Colors, Spacing } from '../constants/theme';
import { Ionicons } from '@expo/vector-icons';

interface PostCardProps {
  post: PostSummary;
  onPress: () => void;
}

export const PostCard: React.FC<PostCardProps> = ({ post, onPress }) => {
  const dateFormatted = new Date(post.updated_at || post.created_at).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.header}>
        <StatusBadge status={post.status} />
        <View style={styles.versionBadge}>
          <Text style={styles.versionText}>v{post.content_version}</Text>
        </View>
      </View>

      <Text style={styles.caption} numberOfLines={3}>
        {post.caption || 'No caption text draft.'}
      </Text>

      {post.hashtags && post.hashtags.length > 0 && (
        <Text style={styles.hashtags} numberOfLines={1}>
          {post.hashtags.map((h) => (h.startsWith('#') ? h : `#${h}`)).join(' ')}
        </Text>
      )}

      <View style={styles.footer}>
        <View style={styles.metaGroup}>
          {post.media_count > 0 && (
            <View style={styles.mediaCountBadge}>
              <Ionicons name="image-outline" size={13} color={Colors.textMuted} />
              <Text style={styles.metaText}>{post.media_count}</Text>
            </View>
          )}
          <Text style={styles.metaText}>{dateFormatted}</Text>
        </View>

        <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  versionBadge: {
    backgroundColor: '#f1f5f9',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  versionText: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.textMuted,
  },
  caption: {
    fontSize: 14,
    lineHeight: 20,
    color: Colors.text,
    marginBottom: Spacing.xs,
  },
  hashtags: {
    fontSize: 12,
    color: Colors.primary,
    fontWeight: '500',
    marginBottom: Spacing.sm,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.xs,
    paddingTop: Spacing.xs,
    borderTopWidth: 1,
    borderTopColor: '#f8fafc',
  },
  metaGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  mediaCountBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    fontSize: 12,
    color: Colors.textMuted,
  },
});

