#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "net/http"
require "uri"

api_base = ENV.fetch("PAPERCLIP_API_URL", "http://localhost:3100").sub(%r{/$}, "")
company_name = ENV.fetch("PAPERCLIP_COMPANY_NAME", "Slope Studio")

def request_json(method, url, body = nil)
  uri = URI(url)
  req_class = {
    get: Net::HTTP::Get,
    post: Net::HTTP::Post,
    patch: Net::HTTP::Patch
  }.fetch(method)
  req = req_class.new(uri)
  req["Content-Type"] = "application/json"
  req.body = JSON.generate(body) if body
  res = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == "https") do |http|
    http.request(req)
  end
  unless res.code.to_i.between?(200, 299)
    raise "#{method.to_s.upcase} #{url} failed: HTTP #{res.code} #{res.body}"
  end
  res.body.nil? || res.body.empty? ? nil : JSON.parse(res.body)
end

def list_items(value)
  return value if value.is_a?(Array)
  return value["items"] if value.is_a?(Hash) && value["items"].is_a?(Array)
  return value["data"] if value.is_a?(Hash) && value["data"].is_a?(Array)
  return value["companies"] if value.is_a?(Hash) && value["companies"].is_a?(Array)
  []
end

def upsert_goal(api_base, company_id, goals_by_title, attrs)
  existing = goals_by_title[attrs.fetch(:title)]
  body = {
    title: attrs.fetch(:title),
    description: attrs[:description],
    level: attrs.fetch(:level),
    status: attrs.fetch(:status),
    parentId: attrs[:parent_id]
  }.compact

  goal = if existing
    request_json(:patch, "#{api_base}/api/goals/#{existing.fetch("id")}", body)
  else
    request_json(:post, "#{api_base}/api/companies/#{company_id}/goals", body)
  end
  goals_by_title[goal.fetch("title")] = goal
  goal
end

companies = list_items(request_json(:get, "#{api_base}/api/companies"))
company = companies.find { |item| item["name"] == company_name }
raise "Company not found by name: #{company_name}" unless company

company_id = company.fetch("id")
goals = list_items(request_json(:get, "#{api_base}/api/companies/#{company_id}/goals"))
goals_by_title = goals.to_h { |goal| [goal.fetch("title"), goal] }

parent_description = <<~MARKDOWN.strip
  Parent goal for the Slope Studio company.

  Full YouTube Partner Program monetization target:
  - 1,000 subscribers
  - and either 4,000 valid public watch hours in the last 12 months
  - or 10,000,000 valid public Shorts views in the last 90 days

  Earlier YPP access target in eligible countries/regions:
  - 500 subscribers
  - 3 valid public uploads in the last 90 days
  - and either 3,000 valid public watch hours in the last 12 months
  - or 3,000,000 valid public Shorts views in the last 90 days

  Readiness checks:
  - follow YouTube channel monetization policies
  - no active Community Guidelines strikes
  - Google Account 2-Step Verification enabled
  - YouTube advanced features access enabled
  - active AdSense for YouTube account linked or ready in YouTube Studio
  - original/authentic content, not mass-produced or repetitive

  Metrics to track:
  - subscribers
  - valid public uploads in last 90 days
  - valid public watch hours in last 365 days
  - valid public Shorts views in last 90 days
  - subscriber conversion by video, topic, title, hook, and traffic source

  Counting rules:
  - Shorts Feed watch hours do not count toward the 4,000 public watch hours threshold
  - private, unlisted, deleted, and ad-campaign views do not count
  - Shorts views must be valid engaged views from public Shorts in the Shorts Feed
MARKDOWN

parent_goal = upsert_goal(
  api_base,
  company_id,
  goals_by_title,
  title: "Unlock Youtube monetization",
  description: parent_description,
  level: "company",
  status: "planned",
  parent_id: nil
)

[
  {
    title: "Reach 1000 subscribers",
    description: "Target: 1,000 subscribers. Track current subscribers, subscribers gained per video, and subscriber conversion by topic, hook, title, and traffic source.",
    level: "task"
  },
  {
    title: "Reach YPP traffic threshold",
    description: "Full monetization needs either 4,000 valid public watch hours in the last 12 months or 10,000,000 valid public Shorts views in the last 90 days. Earlier access needs either 3,000 valid public watch hours in the last 12 months or 3,000,000 valid public Shorts views in the last 90 days.",
    level: "task"
  },
  {
    title: "Pass YPP readiness checks",
    description: "Track monetization policy compliance, YPP-supported country/region, zero active strikes, 2-Step Verification, advanced features access, AdSense readiness, and original/authentic content.",
    level: "task"
  }
].each do |goal|
  upsert_goal(
    api_base,
    company_id,
    goals_by_title,
    title: goal.fetch(:title),
    description: goal.fetch(:description),
    level: goal.fetch(:level),
    status: "planned",
    parent_id: parent_goal.fetch("id")
  )
end

puts "Goals ready for company #{company_name}: Unlock Youtube monetization"
