import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList, GenerationJob, JobStep } from '../types';
import { apiGetJobStatus, apiRetryJob } from '../api/generator';
import { Colors, Spacing, Typography } from '../constants/theme';
import { Ionicons } from '@expo/vector-icons';

type ScreenRouteProp = RouteProp<RootStackParamList, 'GenerationProgress'>;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

interface StepConfig {
  key: JobStep;
  label: string;
  desc: string;
  icon: keyof typeof Ionicons.glyphMap;
}

const STEPS: StepConfig[] = [
  {
    key: 'extracting',
    label: 'Angle & Topic Extraction',
    desc: 'Extracting key themes, hooks, and core premise',
    icon: 'search-outline',
  },
  {
    key: 'researching',
    label: 'Deep Research & Citations',
    desc: 'Finding market data and factual citations',
    icon: 'book-outline',
  },
  {
    key: 'writing',
    label: 'Copy & Hashtag Synthesis',
    desc: 'Crafting hook, body copy, CTA and targeted hashtags',
    icon: 'create-outline',
  },
  {
    key: 'image_generation',
    label: '1080x1080 Social Graphic',
    desc: 'Rendering branded banner asset with Pillow engine',
    icon: 'color-palette-outline',
  },
];

export const GenerationProgressScreen = () => {
  const route = useRoute<ScreenRouteProp>();
  const navigation = useNavigation<NavigationProp>();
  const { jobId } = route.params;

  const [job, setJob] = useState<GenerationJob | null>(null);
  const [retrying, setRetrying] = useState(false);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await apiGetJobStatus(jobId);
      if (res.data) {
        setJob(res.data);
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        }
      }
    } catch {
      // keep polling
    }
  };

  useEffect(() => {
    fetchStatus();
    pollTimerRef.current = setInterval(fetchStatus, 1500);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [jobId]);

  const handleRetry = async () => {
    setRetrying(true);
    await apiRetryJob(jobId);
    setRetrying(false);
    pollTimerRef.current = setInterval(fetchStatus, 1500);
  };

  const getStepStatus = (stepKey: JobStep) => {
    if (!job) return 'pending';
    if (job.status === 'completed') return 'completed';

    const order: JobStep[] = ['extracting', 'researching', 'writing', 'image_generation', 'completed'];
    const currentIndex = order.indexOf(job.current_step);
    const thisIndex = order.indexOf(stepKey);

    if (thisIndex < currentIndex) return 'completed';
    if (thisIndex === currentIndex) return job.status === 'failed' ? 'failed' : 'active';
    return 'pending';
  };

  const progressPct = job?.progress_pct || 15;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>AI Pipeline Execution</Text>
        <Text style={styles.subtitle}>Job ID: {jobId.slice(0, 8)}</Text>
      </View>

      {/* Progress Bar */}
      <View style={styles.progressCard}>
        <View style={styles.progressTop}>
          <Text style={styles.progressLabel}>
            {job?.status === 'completed'
              ? 'Complete'
              : job?.status === 'failed'
              ? 'Failed'
              : 'Generating...'}
          </Text>
          <Text style={styles.progressPercent}>{progressPct}%</Text>
        </View>
        <View style={styles.progressBarTrack}>
          <View
            style={[
              styles.progressBarFill,
              { width: `${progressPct}%` },
              job?.status === 'failed' && { backgroundColor: Colors.danger },
            ]}
          />
        </View>
      </View>

      {/* Steps List */}
      <View style={styles.stepsContainer}>
        {STEPS.map((step, idx) => {
          const status = getStepStatus(step.key);
          return (
            <View key={step.key} style={styles.stepRow}>
              {/* Step indicator node */}
              <View style={styles.nodeColumn}>
                <View
                  style={[
                    styles.node,
                    status === 'completed' && styles.nodeCompleted,
                    status === 'active' && styles.nodeActive,
                    status === 'failed' && styles.nodeFailed,
                  ]}
                >
                  {status === 'completed' ? (
                    <Ionicons name="checkmark" size={16} color="#ffffff" />
                  ) : status === 'active' ? (
                    <ActivityIndicator size="small" color="#ffffff" />
                  ) : status === 'failed' ? (
                    <Ionicons name="alert" size={14} color="#ffffff" />
                  ) : (
                    <Ionicons name={step.icon} size={14} color={Colors.textMuted} />
                  )}
                </View>
                {idx < STEPS.length - 1 && <View style={styles.connectorLine} />}
              </View>

              {/* Step info */}
              <View style={styles.stepInfo}>
                <Text
                  style={[
                    styles.stepLabel,
                    status === 'active' && styles.stepLabelActive,
                    status === 'completed' && styles.stepLabelCompleted,
                  ]}
                >
                  {step.label}
                </Text>
                <Text style={styles.stepDesc}>{step.desc}</Text>
              </View>
            </View>
          );
        })}
      </View>

      {/* Completion or Error Actions */}
      {job?.status === 'completed' && job.post_id && (
        <View style={styles.actionBox}>
          <View style={styles.successBanner}>
            <Ionicons name="checkmark-circle" size={24} color={Colors.success} />
            <Text style={styles.successBannerText}>Content draft generated successfully!</Text>
          </View>

          <TouchableOpacity
            style={styles.primaryActionBtn}
            onPress={() => navigation.replace('PostDetail', { postId: job.post_id! })}
          >
            <Text style={styles.primaryActionText}>Review &amp; Approve Post</Text>
            <Ionicons name="arrow-forward" size={18} color="#ffffff" />
          </TouchableOpacity>
        </View>
      )}

      {job?.status === 'failed' && (
        <View style={styles.actionBox}>
          <View style={styles.errorBanner}>
            <Ionicons name="alert-circle" size={20} color={Colors.danger} />
            <Text style={styles.errorBannerText}>
              {job.error_message || 'Pipeline encountered an unexpected error.'}
            </Text>
          </View>

          <TouchableOpacity
            style={styles.retryBtn}
            onPress={handleRetry}
            disabled={retrying}
          >
            {retrying ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <>
                <Ionicons name="refresh" size={16} color="#ffffff" />
                <Text style={styles.retryBtnText}>Retry Pipeline</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}
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
  header: {
    marginBottom: Spacing.md,
  },
  title: {
    ...Typography.header,
  },
  subtitle: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginTop: 2,
  },
  progressCard: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.lg,
  },
  progressTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.text,
  },
  progressPercent: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.primary,
  },
  progressBarTrack: {
    height: 8,
    borderRadius: 4,
    backgroundColor: '#f1f5f9',
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: Colors.primary,
    borderRadius: 4,
  },
  stepsContainer: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.lg,
  },
  stepRow: {
    flexDirection: 'row',
    minHeight: 64,
  },
  nodeColumn: {
    alignItems: 'center',
    width: 32,
    marginRight: 12,
  },
  node: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#f1f5f9',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  nodeCompleted: {
    backgroundColor: Colors.success,
  },
  nodeActive: {
    backgroundColor: Colors.primary,
  },
  nodeFailed: {
    backgroundColor: Colors.danger,
  },
  connectorLine: {
    width: 2,
    flex: 1,
    backgroundColor: '#e2e8f0',
    marginVertical: 4,
  },
  stepInfo: {
    flex: 1,
    paddingTop: 4,
    paddingBottom: Spacing.sm,
  },
  stepLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textMuted,
    marginBottom: 2,
  },
  stepLabelActive: {
    color: Colors.primary,
    fontWeight: '700',
  },
  stepLabelCompleted: {
    color: Colors.text,
    fontWeight: '600',
  },
  stepDesc: {
    fontSize: 12,
    color: Colors.textMuted,
    lineHeight: 16,
  },
  actionBox: {
    gap: 12,
  },
  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: Colors.successLight,
    padding: Spacing.md,
    borderRadius: 14,
  },
  successBannerText: {
    color: Colors.success,
    fontWeight: '600',
    fontSize: 13,
    flex: 1,
  },
  primaryActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.primary,
    paddingVertical: 14,
    borderRadius: 14,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 4,
  },
  primaryActionText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '700',
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: Colors.dangerLight,
    padding: Spacing.md,
    borderRadius: 14,
  },
  errorBannerText: {
    color: Colors.danger,
    fontSize: 13,
    flex: 1,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.text,
    paddingVertical: 12,
    borderRadius: 12,
  },
  retryBtnText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
});

