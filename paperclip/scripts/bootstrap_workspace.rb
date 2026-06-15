#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "net/http"
require "uri"

api_base = ENV.fetch("PAPERCLIP_API_URL", "http://localhost:3100").sub(%r{/$}, "")
company_name = ENV.fetch("PAPERCLIP_COMPANY_NAME", "Slope Studio")
project_name = ENV.fetch("PAPERCLIP_PROJECT_NAME", "Slope Studio")
workspace_name = ENV.fetch("PAPERCLIP_WORKSPACE_NAME", "Slope Studio local")
workspace_cwd = ENV.fetch("PAPERCLIP_WORKSPACE_CWD", "/Users/dasein/dev/slope-studio")

def request_json(method, url, body = nil)
  uri = URI(url)
  klass = { get: Net::HTTP::Get, post: Net::HTTP::Post, patch: Net::HTTP::Patch }.fetch(method)
  req = klass.new(uri)
  req["Content-Type"] = "application/json"
  req.body = JSON.generate(body) if body
  res = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == "https") { |http| http.request(req) }
  raise "#{method.to_s.upcase} #{url} failed: HTTP #{res.code} #{res.body}" unless res.code.to_i.between?(200, 299)

  res.body.nil? || res.body.empty? ? nil : JSON.parse(res.body)
end

def list_items(value)
  return value if value.is_a?(Array)
  return value["items"] if value.is_a?(Hash) && value["items"].is_a?(Array)
  return value["data"] if value.is_a?(Hash) && value["data"].is_a?(Array)
  return value["companies"] if value.is_a?(Hash) && value["companies"].is_a?(Array)

  []
end

companies = list_items(request_json(:get, "#{api_base}/api/companies"))
company = companies.find { |item| item["name"] == company_name && item["status"] == "active" } ||
          companies.find { |item| item["name"] == company_name }
raise "Company not found by name: #{company_name}" unless company

company_id = company.fetch("id")
projects = list_items(request_json(:get, "#{api_base}/api/companies/#{company_id}/projects"))
project = projects.find { |item| item["name"] == project_name } ||
          projects.find { |item| item["urlKey"] == "slope-studio" }
raise "Project not found by name: #{project_name}" unless project

project_id = project.fetch("id")
workspaces = list_items(request_json(:get, "#{api_base}/api/projects/#{project_id}/workspaces"))
existing = workspaces.find { |workspace| workspace["cwd"] == workspace_cwd }

if existing
  request_json(
    :patch,
    "#{api_base}/api/projects/#{project_id}/workspaces/#{existing.fetch("id")}",
    {
      name: workspace_name,
      sourceType: "local_path",
      cwd: workspace_cwd,
      isPrimary: true,
      visibility: "default"
    }
  )
else
  request_json(
    :post,
    "#{api_base}/api/projects/#{project_id}/workspaces",
    {
      name: workspace_name,
      sourceType: "local_path",
      cwd: workspace_cwd,
      isPrimary: true,
      visibility: "default"
    }
  )
end

request_json(
  :patch,
  "#{api_base}/api/projects/#{project_id}",
  {
    executionWorkspacePolicy: {
      enabled: true,
      defaultMode: "shared_workspace",
      allowIssueOverride: true
    }
  }
)

puts "Workspace ready for project #{project_name}: #{workspace_cwd}"
