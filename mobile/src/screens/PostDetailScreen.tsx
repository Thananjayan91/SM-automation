import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRoute, RouteProp } from '@react-navigation/native';
import { RootStackParamList, PostDetail } from '../types';
import { apiGetPost, apiApprovePost } from '../api/posts';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { Colors, Spacing, Typography } from '../constants/theme';
import { Ionicons } from '@expo/vector-icons';

type ScreenRouteProp = RouteProp<RootStackParamList, 'PostDetail'>;

export const PostDetailScreen = () => {
  const route = useRoute<ScreenRouteProp>();
  const { postId } = route.params;
  const { serverUrl } = useAuth();

  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);

  const fetchPost = async () => {
    try {
      const res = await apiGetPost(postId);
      if (res.data) {
        setPost(res.data);
      }
    } catch {
      // keep quiet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPost();
  }, [postId]);

  const handleApprove = async () => {
    if (!post) return;
    setApproving(true);
    const res = await apiApprovePost(post.id, post.content_version);
    setApproving(false);

    if (res.data) {
      Alert.alert(
        'Version Approved!',
        `Version ${post.content_version} has been formally signed off for publishing.`
      );
      fetchPost();
    } else {
      Alert.alert('Approval Failed', res.error || 'Could not approve version.');
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading post details...</Text>
      </View>
    );
  }

  if (!post) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Post not found.</Text>
      </View>
    );
  }

  // Construct absolute image URL if relative
  let mediaUrl: string | null = null;
  if (post.media && post.media.length > 0) {
    const rawUrl = post.media[0].url;
    mediaUrl = rawUrl.startsWith('http') ? rawUrl : `${serverUrl}${rawUrl}`;
  }

  const isApproved = post.status === 'approved' || post.status === 'published';

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Status Bar */}
      <View style={styles.statusRow}>
        <StatusBadge status={post.status} />
        <View style={styles.versionChip}>
          <Ionicons name="git-commit-outline" size={14} color={Colors.primary} />
          <Text style={styles.versionChipText}>Version {post.content_version}</Text>
        </View>
      </View>

      {/* Social Card Preview */}
      <View style={styles.previewCard}>
        {/* Author header */}
        <View style={styles.cardHeader}>
          <View style={styles.avatar}>
            <Ionicons name="sparkles" size={16} color="#ffffff" />
          </View>
          <View>
            <Text style={styles.brandName}>AI Social Studio</Text>
            <Text style={styles.postDate}>
              {new Date(post.created_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </Text>
          </View>
        </View>

        {/* Caption */}
        <Text style={styles.captionText}>{post.caption || 'No caption text provided.'}</Text>

        {/* Hashtags */}
        {post.hashtags && post.hashtags.length > 0 && (
          <Text style={styles.hashtagsText}>
            {post.hashtags.map((h) => (h.startsWith('#') ? h : `#${h}`)).join(' ')}
          </Text>
        )}

        {/* Media Graphic */}
        {mediaUrl && (
          <View style={styles.imageContainer}>
            <Image
              source={{ uri: mediaUrl }}
              style={styles.bannerImage}
              resizeMode="cover"
            />
          </View>
        )}

        {/* First comment banner */}
        {post.first_comment_enabled && post.first_comment && (
          <View style={styles.firstCommentBox}>
            <View style={styles.firstCommentHeader}>
              <Ionicons name="chatbubble-ellipses-outline" size={13} color={Colors.primary} />
              <Text style={styles.firstCommentTitle}>First Comment Automation</Text>
            </View>
            <Text style={styles.firstCommentContent}>{post.first_comment}</Text>
          </View>
        )}
      </View>

      {/* Target Destinations */}
      <View style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>Publishing Channels</Text>
        {post.targets && post.targets.length > 0 ? (
          <View style={styles.targetsList}>
            {post.targets.map((t) => (
              <View key={t.id} style={styles.targetRow}>
                <View style={styles.targetIcon}>
                  <Ionicons
                    name={
                      t.platform === 'facebook'
                        ? 'logo-facebook'
                        : t.platform === 'instagram'
                        ? 'logo-instagram'
                        : 'share-social-outline'
                    }
                    size={16}
                    color="#ffffff"
                  />
                </View>
                <View style={styles.targetInfo}>
                  <Text style={styles.targetName}>
                    {t.display_name || `${t.platform.toUpperCase()} Page`}
                  </Text>
                  <Text style={styles.targetStatus}>{t.status.toUpperCase()}</Text>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.noTargetsText}>No publishing targets configured yet.</Text>
        )}
      </View>

      {/* 1-Tap Version Approval Button */}
      <View style={styles.actionSection}>
        {isApproved ? (
          <View style={styles.approvedNotice}>
            <Ionicons name="checkmark-done-circle" size={20} color={Colors.success} />
            <Text style={styles.approvedNoticeText}>
              Version {post.content_version} is formally approved and locked.
            </Text>
          </View>
        ) : (
          <TouchableOpacity
            style={[styles.approveBtn, approving && styles.btnDisabled]}
            onPress={handleApprove}
            disabled={approving}
          >
            {approving ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <View style={styles.btnRow}>
                <Ionicons name="checkmark-circle" size={20} color="#ffffff" />
                <Text style={styles.approveBtnText}>
                  Approve Version {post.content_version}
                </Text>
              </View>
            )}
          </TouchableOpacity>
        )}
      </View>
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
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.xl,
  },
  loadingText: {
    fontSize: 14,
    color: Colors.textMuted,
    marginTop: 10,
  },
  errorText: {
    fontSize: 15,
    color: Colors.danger,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  versionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.primaryLight,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  versionChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.primary,
  },
  previewCard: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: Spacing.md,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandName: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.text,
  },
  postDate: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  captionText: {
    fontSize: 14,
    lineHeight: 21,
    color: Colors.text,
    marginBottom: Spacing.sm,
  },
  hashtagsText: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.primary,
    fontWeight: '600',
    marginBottom: Spacing.md,
  },
  imageContainer: {
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#0f172a',
    marginBottom: Spacing.md,
  },
  bannerImage: {
    width: '100%',
    aspectRatio: 1,
  },
  firstCommentBox: {
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: Spacing.sm,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  firstCommentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  firstCommentTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.primary,
    textTransform: 'uppercase',
  },
  firstCommentContent: {
    fontSize: 12,
    color: Colors.textMuted,
  },
  sectionCard: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.text,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: Spacing.sm,
  },
  targetsList: {
    gap: 8,
  },
  targetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#f8fafc',
    padding: Spacing.sm,
    borderRadius: 10,
  },
  targetIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#1877F2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  targetInfo: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  targetName: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.text,
  },
  targetStatus: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.textMuted,
  },
  noTargetsText: {
    fontSize: 13,
    color: Colors.textMuted,
  },
  actionSection: {
    marginTop: Spacing.xs,
  },
  approveBtn: {
    backgroundColor: Colors.primary,
    paddingVertical: 15,
    borderRadius: 14,
    alignItems: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 4,
  },
  btnDisabled: {
    opacity: 0.7,
  },
  btnRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  approveBtnText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '700',
  },
  approvedNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: Colors.successLight,
    padding: Spacing.md,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  approvedNoticeText: {
    color: Colors.success,
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
});

